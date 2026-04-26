"""
server.py — AgentForge Web Server (Frontend + API)

Serves a modern static frontend from ./frontend and exposes a small REST API
to run the backend pipeline (perspective → extractor → confirm → builder → verifier).

Guardrails integrated:
  G1  — Input validation + prompt injection detection
  G2  — Per-user rate limiting + concurrent job limits
  G3  — Security scanning between builder and verifier
  G4  — Agent spec + verifier output validation
  G5C — HTTP security headers
  G6  — Subprocess timeouts, max concurrent jobs, job auto-expiry
  G7  — Structured JSON logging

Endpoints:
  GET  /                  → frontend/index.html
  GET  /<path>            → frontend static files
  POST /api/auth/signup   → register new user
  POST /api/auth/login    → login and get token
  GET  /api/auth/me       → get current user from token
  POST /api/auth/logout   → invalidate token
  POST /api/generate      → run perspective + extractor (await confirm)  [auth required]
  POST /api/confirm/<id>  → confirm spec and run generation loop         [auth required]
  GET  /api/status/<id>   → poll job status
  GET  /api/result/<id>   → fetch final artifacts
  GET  /api/history       → latest prompts from input.csv
"""

import csv
import json
import os
import subprocess
import sys
import threading
import time
import uuid
import tempfile
from datetime import datetime
from functools import wraps
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from flask import Flask, abort, g, jsonify, request, send_from_directory
from flask_cors import CORS


load_dotenv(dotenv_path=find_dotenv(), override=True)

import auth  # noqa: E402  —  must be after dotenv so AUTH_SECRET_KEY can be read

# G1, G2, G4, G6C, G7
from guardrails import (
    validate_prompt,
    detect_prompt_injection,
    llm_content_check,
    validate_agent_spec,
    validate_verifier_result,
    PIPELINE_LIMITER,
    API_LIMITER,
    AUTH_LIMITER,
    user_has_active_job,
    count_active_jobs,
    cleanup_stale_jobs,
    MAX_CONCURRENT_JOBS,
    log,
)

# G3
from security_scanner import scan_project, strip_hardcoded_secrets

BASE_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = BASE_DIR / "frontend"
PYTHON = sys.executable

# Force UTF-8 for subprocess outputs on Windows
SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

# Backend scripts
PERSPECTIVE_AGENT = BASE_DIR / "perspective_agent.py"
INPUT_EXTRACTOR = BASE_DIR / "inputextractor.py"
AGENT_BUILD = BASE_DIR / "agentbuild.py"
VERIFIER_AGENT = BASE_DIR / "verifier.py"

# Persistent prompt history only; run artifacts are job-local temp files.
INPUT_CSV = BASE_DIR / "input.csv"


app = Flask(__name__, static_folder=str(FRONTEND_DIR))

# CORS — Allow cross-origin requests from Vercel frontend + localhost for dev
# Update the origins list with your actual Vercel deployment URL
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "https://*.vercel.app",   # All Vercel preview deployments
            # Add your custom domain here if you have one:
            # "https://yourdomain.com",
        ],
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "OPTIONS"],
    }
})

jobs: dict = {}
CONTENT_GUARD_ENABLED = os.getenv("CONTENT_GUARD_ENABLED", "false").strip().lower() == "true"

PIPELINE_STEPS = [
    {
        "id": "perspective",
        "name": "Perspective Agent",
        "description": "Classify input as agent-building or conversational",
        "icon": "🔍",
    },
    {
        "id": "extractor",
        "name": "Input Extractor",
        "description": "Extract agent specifications into structured JSON",
        "icon": "📋",
    },
    {
        "id": "security",
        "name": "Security Scanner",
        "description": "Scan generated code for secrets, dangerous calls, exfiltration",
        "icon": "🛡️",
    },
    {
        "id": "builder",
        "name": "Code Generator",
        "description": "Generate agent.py + main.py + requirements.txt + README.md",
        "icon": "⚙️",
    },
    {
        "id": "verifier",
        "name": "Verifier Agent",
        "description": "Review correctness against spec (Syntax + Compliance + LLM)",
        "icon": "✅",
    },
]


# ─────────────────────────────────────────────
#  G5C — HTTP SECURITY HEADERS
# ─────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    """Add security headers to every response (G5C)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com;"
    )
    # Never cache API responses
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ─────────────────────────────────────────────
#  AUTH MIDDLEWARE
# ─────────────────────────────────────────────

def require_auth(f):
    """Decorator that requires a valid auth token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        user = auth.get_user_from_token(token)
        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.user = user
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  STATIC FILES
# ─────────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/<path:filename>")
def serve_static(filename: str):
    if filename.startswith("api/") or filename == "api":
        abort(404)
    return send_from_directory(str(FRONTEND_DIR), filename)


# ─────────────────────────────────────────────
#  AUTH ENDPOINTS (with G2 rate limiting)
# ─────────────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    # G2 — Rate limit auth attempts by IP (use 0 as pseudo user-id for anon)
    ip_hash = hash(request.remote_addr or "unknown") % 10**8
    allowed, wait = AUTH_LIMITER.is_allowed(ip_hash)
    if not allowed:
        log.warn("auth_rate_limit", endpoint="signup", ip_hash=ip_hash, retry_after=wait)
        return jsonify({"error": f"Too many attempts. Try again in {wait}s.", "retry_after": wait}), 429

    data = request.get_json() or {}
    result = auth.signup(
        username=str(data.get("username", "")),
        email=str(data.get("email", "")),
        password=str(data.get("password", "")),
    )
    if result["success"]:
        log.info("user_signup", username=data.get("username", ""))
        # Auto-login after signup
        login_result = auth.login(
            email=str(data.get("email", "")),
            password=str(data.get("password", "")),
        )
        if login_result["success"]:
            return jsonify(login_result)
        return jsonify(result)
    return jsonify(result), 400


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    # G2 — Rate limit auth attempts by IP
    ip_hash = hash(request.remote_addr or "unknown") % 10**8
    allowed, wait = AUTH_LIMITER.is_allowed(ip_hash)
    if not allowed:
        log.warn("auth_rate_limit", endpoint="login", ip_hash=ip_hash, retry_after=wait)
        return jsonify({"error": f"Too many attempts. Try again in {wait}s.", "retry_after": wait}), 429

    data = request.get_json() or {}
    result = auth.login(
        email=str(data.get("email", "")),
        password=str(data.get("password", "")),
    )
    if result["success"]:
        log.info("user_login", user_id=result["user"]["id"], username=result["user"]["username"])
        return jsonify(result)
    log.warn("login_failed", email=str(data.get("email", ""))[:30])
    return jsonify(result), 401


@app.route("/api/auth/me")
def api_me():
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        return jsonify({"error": "No token provided"}), 401
    user = auth.get_user_from_token(token)
    if not user:
        return jsonify({"error": "Invalid or expired token"}), 401
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if token:
        auth.logout(token)
    return jsonify({"success": True})


# ─────────────────────────────────────────────
#  PIPELINE HELPERS
# ─────────────────────────────────────────────

def save_input_to_csv(user_input: str) -> None:
    file_exists = INPUT_CSV.exists()
    with open(INPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_input"])
        writer.writerow([datetime.now().isoformat(), user_input])


def _job_paths(job_id: str) -> dict[str, str]:
    run_dir = Path(tempfile.gettempdir()) / "agentforge" / job_id
    generated_dir = run_dir / "generated_agent"
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": str(run_dir),
        "input_csv": str(run_dir / "input.csv"),
        "build_agent_output": str(run_dir / "build_agent_output.json"),
        "conversational_output": str(run_dir / "conversational_output.json"),
        "final_agent_json": str(run_dir / "final_agent.json"),
        "generated_dir": str(generated_dir),
        "generated_agent_py": str(generated_dir / "agent.py"),
        "generated_main_py": str(generated_dir / "main.py"),
        "verifier_result": str(run_dir / "verifier_result.json"),
    }


def _run_subprocess(
    command: list[str],
    timeout: int = 120,
    input_data: str | None = None,
    env: dict | None = None,
    cwd: str | None = None,
):
    """
    Run a subprocess with hard timeout (G6A).
    Default timeout reduced to 120s (2 min) per step.
    """
    try:
        return subprocess.run(
            command,
            cwd=cwd or str(BASE_DIR),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            input=input_data,
            env={**SUBPROCESS_ENV, **(env or {})},
        )
    except subprocess.TimeoutExpired as e:
        log.error("subprocess_timeout", command=str(command[-1]), timeout=timeout)
        # Return a fake CompletedProcess with error info
        return subprocess.CompletedProcess(
            args=command,
            returncode=-1,
            stdout="",
            stderr=f"Process timed out after {timeout} seconds",
        )


def _verdict_from_score(score: float | int | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 85:
        return "READY"
    if score >= 75:
        return "ACCEPTABLE"
    if score >= 60:
        return "PARTIAL"
    return "REJECT"


def _set_step_status(job: dict, step_id: str, status: str, error: str | None = None) -> None:
    for step in job["steps"]:
        if step["id"] == step_id:
            step["status"] = status
            step["error"] = error
            return


def _is_termination_requested(job: dict) -> bool:
    return bool(job.get("terminate_requested"))


def _mark_terminated(job: dict, reason: str = "Run terminated by user.") -> None:
    job["status"] = "terminated"
    job["error"] = reason
    for step in job.get("steps", []):
        if step.get("status") in ("pending", "running", "waiting"):
            step["status"] = "skipped"
    log.warn("job_terminated", job_id=job.get("id"), reason=reason)


# ─────────────────────────────────────────────
#  G3 — SECURITY SCAN (between builder & verifier)
# ─────────────────────────────────────────────

def _run_security_scan(job: dict) -> bool:
    """
    Run G3 security scanner on generated code.
    Auto-remediates hardcoded secrets if found.

    Returns True if scan passed (possibly after remediation), False if hard block.
    """
    _set_step_status(job, "security", "running")
    log.info("security_scan_start", job_id=job["id"])

    try:
        generated_dir = job["paths"]["generated_dir"]
        scan_result = scan_project(generated_dir)
        job["security_scan"] = {
            "clean": scan_result["clean"],
            "total_issues": scan_result["total_issues"],
            "total_warnings": scan_result["total_warnings"],
            "files": {
                fname: {
                    "issues": s["issues"],
                    "warnings": s["warnings"],
                    "clean": s["clean"],
                }
                for fname, s in scan_result["files"].items()
            },
            "req_warnings": scan_result.get("req_warnings", []),
        }

        if not scan_result["clean"]:
            # Attempt auto-remediation for hardcoded secrets
            remediated = False
            for fname in ["agent.py", "main.py"]:
                fpath = Path(generated_dir) / fname
                if fpath.exists():
                    original = fpath.read_text(encoding="utf-8")
                    cleaned = strip_hardcoded_secrets(original)
                    if cleaned != original:
                        fpath.write_text(cleaned, encoding="utf-8")
                        remediated = True
                        log.info("secret_auto_remediated", filename=fname, job_id=job["id"])

            if remediated:
                # Re-scan after remediation
                rescan = scan_project(generated_dir)
                job["security_scan"]["remediated"] = True
                job["security_scan"]["post_remediation_issues"] = rescan["total_issues"]

                if rescan["clean"]:
                    _set_step_status(job, "security", "done")
                    log.info("security_scan_passed_after_remediation", job_id=job["id"])
                    return True

            # Still has issues after remediation
            all_issues = []
            for s in scan_result["files"].values():
                all_issues.extend(s["issues"])
            issue_summary = "; ".join(all_issues[:3])  # Cap at 3 for display
            _set_step_status(job, "security", "error", f"Security issues: {issue_summary}")
            log.security("security_scan_failed", job_id=job["id"], issues=all_issues)
            return False
        else:
            _set_step_status(job, "security", "done")
            log.info("security_scan_passed", job_id=job["id"], warnings=scan_result["total_warnings"])
            return True

    except Exception as e:
        # Don't block pipeline on scanner errors — just warn
        _set_step_status(job, "security", "done")
        log.error("security_scan_exception", job_id=job["id"], error=str(e))
        return True


# ─────────────────────────────────────────────
#  GENERATION WITH RETRIES + SECURITY SCAN
# ─────────────────────────────────────────────

def _run_generation_with_retries(job: dict) -> None:
    max_regen_retries = 2
    partial_regenerated = False
    attempts = []

    run_env = {
        "FINAL_AGENT_JSON_PATH": job["paths"]["final_agent_json"],
        "GENERATED_AGENT_DIR": job["paths"]["generated_dir"],
        "GENERATED_AGENT_PY_PATH": job["paths"]["generated_agent_py"],
        "GENERATED_MAIN_PY_PATH": job["paths"]["generated_main_py"],
        "VERIFIER_RESULT_PATH": job["paths"]["verifier_result"],
    }

    for attempt in range(1, max_regen_retries + 2):
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        attempt_record = {"attempt": attempt}

        # Step: Builder
        job["current_step"] = 3
        _set_step_status(job, "builder", "running")
        log.info("builder_start", job_id=job["id"], attempt=attempt)
        builder = _run_subprocess([PYTHON, str(AGENT_BUILD)], timeout=300, env=run_env)
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if builder.returncode != 0:
            err_msg = builder.stderr[-800:] if builder.stderr else "Unknown builder error"
            _set_step_status(job, "builder", "error", err_msg)
            attempt_record["builder_error"] = err_msg
            log.error("builder_failed", job_id=job["id"], attempt=attempt)
            attempts.append(attempt_record)
            if attempt <= max_regen_retries:
                continue
            job["status"] = "error"
            job["error"] = f"Code generation failed after {attempt} attempts"
            job["attempts"] = attempts
            return
        _set_step_status(job, "builder", "done")
        log.info("builder_done", job_id=job["id"], attempt=attempt)

        # G3 — Security Scan (between builder and verifier)
        job["current_step"] = 2
        security_passed = _run_security_scan(job)
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if not security_passed:
            attempt_record["security_failed"] = True
            attempts.append(attempt_record)
            if attempt <= max_regen_retries:
                log.warn("regenerating_after_security_fail", job_id=job["id"], attempt=attempt)
                continue
            # Max retries exhausted — still deliver with security warning
            log.security(
                "delivering_with_security_issues",
                job_id=job["id"],
                attempts=attempt,
            )

        # Step: Verifier (Syntax + Compliance + LLM)
        job["current_step"] = 4
        _set_step_status(job, "verifier", "running")
        log.info("verifier_start", job_id=job["id"], attempt=attempt)
        verifier = _run_subprocess([PYTHON, str(VERIFIER_AGENT)], timeout=240, env=run_env)
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if verifier.returncode != 0:
            err_msg = verifier.stderr[-800:] if verifier.stderr else "Verifier execution failed"
            _set_step_status(job, "verifier", "error", err_msg)
            attempt_record["verifier_error"] = err_msg
            log.error("verifier_failed", job_id=job["id"], attempt=attempt)
            attempts.append(attempt_record)
            if attempt <= max_regen_retries:
                continue
            job["status"] = "error"
            job["error"] = f"Verification failed after {attempt} attempts"
            job["attempts"] = attempts
            return

        verifier_result = {}
        verifier_result_path = Path(job["paths"]["verifier_result"])
        if verifier_result_path.exists():
            try:
                verifier_result = json.loads(verifier_result_path.read_text(encoding="utf-8"))
            except Exception:
                verifier_result = {}

        # G4B — Validate verifier LLM output before trusting score
        llm_details = verifier_result.get("layer3_llm", {}).get("details", {})
        is_valid, val_err = validate_verifier_result(llm_details)
        if not is_valid:
            log.warn("verifier_output_invalid", job_id=job["id"], error=val_err)
            # Fall back to layer1 + layer2 scores only
            if "correctness_score" not in verifier_result:
                verifier_result["correctness_score"] = 50  # conservative default

        score = verifier_result.get("correctness_score")
        band = verifier_result.get("correctness_band") or _verdict_from_score(score)
        attempt_record["correctness_score"] = score
        attempt_record["correctness_band"] = band
        attempt_record["security_clean"] = job.get("security_scan", {}).get("clean", True)
        attempts.append(attempt_record)

        log.info(
            "verification_done",
            job_id=job["id"],
            attempt=attempt,
            score=score,
            band=band,
        )

        if band == "REJECT" and attempt <= max_regen_retries:
            _set_step_status(job, "verifier", "pending")
            continue

        if band == "PARTIAL" and (not partial_regenerated) and attempt <= max_regen_retries:
            partial_regenerated = True
            _set_step_status(job, "verifier", "pending")
            continue

        _set_step_status(job, "verifier", "done")
        verifier_result["delivery_decision"] = band
        verifier_result["delivery_notes"] = (
            "Ready to deliver to engineer."
            if band == "READY"
            else "Deliver with verification notes."
            if band == "ACCEPTABLE"
            else "Partial quality: best-attempt delivery after one regeneration."
            if band == "PARTIAL"
            else "Rejected by score threshold."
        )
        verifier_result["regeneration_attempts"] = attempt - 1
        verifier_result["security_scan"] = job.get("security_scan", {})
        job["verifier_result"] = verifier_result
        job["attempts"] = attempts
        job["status"] = "done"
        job["current_step"] = 5
        log.info("pipeline_complete", job_id=job["id"], score=score, band=band)
        return


# ─────────────────────────────────────────────
#  PIPELINE EXECUTION
# ─────────────────────────────────────────────

def run_pipeline(job_id: str, prompt: str) -> None:
    job = jobs[job_id]
    try:
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        save_input_to_csv(prompt)
        job["prompt"] = prompt
        log.info("pipeline_start", job_id=job_id, prompt_length=len(prompt), user=job.get("user"))

        # Seed run-local input.csv for scripts that read latest prompt from CSV.
        run_input_csv = Path(job["paths"]["input_csv"])
        with run_input_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "user_input"])
            writer.writerow([datetime.now().isoformat(), prompt])

        run_env = {
            "INPUT_CSV_PATH": job["paths"]["input_csv"],
            "BUILD_AGENT_OUTPUT_PATH": job["paths"]["build_agent_output"],
            "CONVERSATIONAL_OUTPUT_PATH": job["paths"]["conversational_output"],
            "FINAL_AGENT_JSON_PATH": job["paths"]["final_agent_json"],
            "GENERATED_AGENT_DIR": job["paths"]["generated_dir"],
            "GENERATED_AGENT_PY_PATH": job["paths"]["generated_agent_py"],
            "GENERATED_MAIN_PY_PATH": job["paths"]["generated_main_py"],
            "VERIFIER_RESULT_PATH": job["paths"]["verifier_result"],
        }

        # Step 1: Perspective
        job["current_step"] = 0
        job["steps"][0]["status"] = "running"
        result = _run_subprocess([PYTHON, str(PERSPECTIVE_AGENT)], timeout=180, env=run_env)
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if result.returncode != 0:
            job["steps"][0]["status"] = "error"
            job["steps"][0]["error"] = result.stderr[-800:] if result.stderr else "Unknown error"
            job["status"] = "error"
            job["error"] = f"Perspective Agent failed: {job['steps'][0]['error']}"
            log.error("perspective_failed", job_id=job_id)
            return

        job["steps"][0]["status"] = "done"

        # Conversational short-circuit
        conversational_output_path = Path(job["paths"]["conversational_output"])
        if conversational_output_path.exists():
            try:
                conv = json.loads(conversational_output_path.read_text(encoding="utf-8"))
            except Exception:
                conv = {}
            job["route"] = "conversational"
            job["conversational_response"] = conv.get("conversational_response", "")
            job["classification"] = conv
            for i in range(1, len(job["steps"])):
                job["steps"][i]["status"] = "skipped"
            job["status"] = "done"
            job["current_step"] = 5
            log.info("pipeline_conversational", job_id=job_id)
            return

        job["route"] = "agent_building"
        build_output_path = Path(job["paths"]["build_agent_output"])
        if build_output_path.exists():
            try:
                job["classification"] = json.loads(build_output_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Step 2: Extractor
        job["current_step"] = 1
        job["steps"][1]["status"] = "running"
        result = _run_subprocess([PYTHON, str(INPUT_EXTRACTOR)], timeout=300, input_data="yes\n", env=run_env)
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if result.returncode != 0:
            job["steps"][1]["status"] = "error"
            job["steps"][1]["error"] = result.stderr[-800:] if result.stderr else "Unknown error"
            job["status"] = "error"
            job["error"] = f"Input Extractor failed: {job['steps'][1]['error']}"
            log.error("extractor_failed", job_id=job_id)
            return
        job["steps"][1]["status"] = "done"

        final_agent_path = Path(job["paths"]["final_agent_json"])
        if final_agent_path.exists():
            try:
                job["agent_spec"] = json.loads(final_agent_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # G4A — Validate agent spec before confirmation
        if job.get("agent_spec"):
            is_valid, spec_errors = validate_agent_spec(job["agent_spec"])
            job["spec_validation"] = {"valid": is_valid, "errors": spec_errors}
            if spec_errors:
                log.warn("agent_spec_validation_warnings", job_id=job_id, errors=spec_errors)

        # Pause for user confirmation
        job["status"] = "awaiting_confirmation"
        for step in job["steps"][2:]:
            step["status"] = "waiting"
        log.info("awaiting_confirmation", job_id=job_id)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        log.error("pipeline_exception", job_id=job_id, error=str(e))


def run_generation_after_confirmation(job_id: str) -> None:
    job = jobs[job_id]
    try:
        if _is_termination_requested(job):
            _mark_terminated(job)
            return
        if not job.get("agent_spec"):
            job["status"] = "error"
            job["error"] = "No confirmed JSON spec available"
            return

        # G4A — Re-validate spec after user edits
        is_valid, spec_errors = validate_agent_spec(job["agent_spec"])
        if not is_valid:
            job["status"] = "error"
            job["error"] = f"Invalid agent spec: {'; '.join(spec_errors[:3])}"
            log.error("spec_validation_failed_post_confirm", job_id=job_id, errors=spec_errors)
            return

        final_spec_path = Path(job["paths"]["final_agent_json"])
        final_spec_path.write_text(json.dumps(job["agent_spec"], indent=2), encoding="utf-8")
        job["status"] = "running"
        log.info("generation_after_confirm", job_id=job_id)
        _run_generation_with_retries(job)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        log.error("generation_exception", job_id=job_id, error=str(e))


# ─────────────────────────────────────────────
#  API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
@require_auth
def generate():
    data = request.get_json() or {}
    prompt = str(data.get("prompt", "")).strip()
    user = g.user
    user_id = user.get("id", 0)

    # G1A — Input validation
    is_valid, validated = validate_prompt(prompt)
    if not is_valid:
        return jsonify({"error": validated}), 400
    prompt = validated

    # G1B — Prompt injection detection
    is_injection, injection_msg = detect_prompt_injection(prompt)
    if is_injection:
        log.security("injection_blocked", user_id=user_id, prompt_length=len(prompt))
        return jsonify({"error": injection_msg}), 400

    # G1C — Optional LLM content moderation
    content_ok, content_msg = llm_content_check(prompt, enabled=CONTENT_GUARD_ENABLED)
    if not content_ok:
        return jsonify({"error": content_msg}), 400

    # G2 — Rate limiting (per user, pipeline-level)
    allowed, wait = PIPELINE_LIMITER.is_allowed(user_id)
    if not allowed:
        return jsonify({
            "error": f"Rate limit reached. Try again in {wait} seconds.",
            "retry_after": wait,
        }), 429

    # G6B — Concurrent job limits (per user)
    if user_has_active_job(jobs, user_id):
        return jsonify({"error": "You already have an active job. Wait for it to finish."}), 429

    # G6B — Server-wide concurrent job cap
    if count_active_jobs(jobs) >= MAX_CONCURRENT_JOBS:
        return jsonify({"error": "Server busy. Please try again shortly."}), 503

    log.info("generate_request", user_id=user_id, prompt_length=len(prompt))

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "prompt": prompt,
        "user": user.get("username", "anonymous"),
        "user_id": user_id,
        "status": "running",
        "route": None,
        "current_step": 0,
        "steps": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "icon": s["icon"],
                "status": "pending",
                "error": None,
            }
            for s in PIPELINE_STEPS
        ],
        "classification": None,
        "agent_spec": None,
        "spec_validation": None,
        "security_scan": None,
        "verifier_result": None,
        "conversational_response": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "paths": _job_paths(job_id),
        "attempts": [],
        "terminate_requested": False,
    }

    thread = threading.Thread(target=run_pipeline, args=(job_id, prompt), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/confirm/<job_id>", methods=["POST"])
@require_auth
def confirm(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job.get("status") != "awaiting_confirmation":
        return jsonify({"error": "Job is not waiting for confirmation"}), 400
    if int(job.get("user_id", -1)) != int(g.user.get("id", -2)):
        return jsonify({"error": "Not authorized for this job"}), 403

    data = request.get_json() or {}
    spec = data.get("agent_spec")
    if not isinstance(spec, dict):
        return jsonify({"error": "agent_spec must be a JSON object"}), 400

    # G4A — Validate the confirmed spec
    is_valid, spec_errors = validate_agent_spec(spec)
    if not is_valid:
        return jsonify({"error": f"Invalid spec: {'; '.join(spec_errors[:3])}"}), 400

    job["agent_spec"] = spec
    log.info("spec_confirmed", job_id=job_id, user=g.user.get("username"))
    thread = threading.Thread(target=run_generation_after_confirmation, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/terminate/<job_id>", methods=["POST"])
@require_auth
def terminate(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if int(job.get("user_id", -1)) != int(g.user.get("id", -2)):
        return jsonify({"error": "Not authorized for this job"}), 403
    if job.get("status") in ("done", "error", "terminated"):
        return jsonify({"error": f"Job already {job.get('status')}"}), 400

    job["terminate_requested"] = True
    log.warn("terminate_requested", job_id=job_id, user=g.user.get("username"))
    return jsonify({"success": True, "status": "terminating"})


@app.route("/api/status/<job_id>")
@require_auth
def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if int(job.get("user_id", -1)) != int(g.user.get("id", -2)):
        return jsonify({"error": "Not authorized for this job"}), 403
    return jsonify(
        {
            "id": job["id"],
            "status": job["status"],
            "route": job["route"],
            "current_step": job["current_step"],
            "steps": job["steps"],
            "error": job["error"],
            "terminate_requested": bool(job.get("terminate_requested")),
            "spec_validation": job.get("spec_validation"),
            "verified_score": (
                (job.get("verifier_result") or {}).get("correctness_score")
                if isinstance(job.get("verifier_result"), dict)
                else None
            ),
        }
    )


@app.route("/api/result/<job_id>")
@require_auth
def result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if int(job.get("user_id", -1)) != int(g.user.get("id", -2)):
        return jsonify({"error": "Not authorized for this job"}), 403

    result_data = {
        "id": job["id"],
        "status": job["status"],
        "route": job["route"],
        "prompt": job["prompt"],
        "classification": job["classification"],
        "agent_spec": job["agent_spec"],
        "spec_validation": job.get("spec_validation"),
        "security_scan": job.get("security_scan"),
        "verifier_result": job["verifier_result"],
        "conversational_response": job["conversational_response"],
        "next_step_hint": (
            'If you want me to build an agent, submit an agent-generation prompt like: "Build me an agent that ..."'
            if job.get("route") == "conversational"
            else None
        ),
        "files": {},
        "attempts": job.get("attempts", []),
        "terminate_requested": bool(job.get("terminate_requested")),
    }

    generated_dir = Path(job["paths"]["generated_dir"])
    if generated_dir.is_dir():
        for fname in ["agent.py", "main.py", "requirements.txt", "README.md"]:
            fpath = generated_dir / fname
            if fpath.exists():
                try:
                    result_data["files"][fname] = fpath.read_text(encoding="utf-8")
                except Exception:
                    result_data["files"][fname] = "[Error reading file]"

    return jsonify(result_data)


@app.route("/api/history")
@require_auth
def history():
    # G2 — generic API-level rate limiting
    user_id = int(g.user.get("id", 0))
    allowed, wait = API_LIMITER.is_allowed(user_id)
    if not allowed:
        return jsonify({"error": f"Too many requests. Retry in {wait}s.", "retry_after": wait}), 429

    entries = []
    if INPUT_CSV.exists():
        try:
            with open(INPUT_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append({"timestamp": row.get("timestamp", ""), "prompt": row.get("user_input", "")})
        except Exception:
            pass
    entries.reverse()
    return jsonify(entries[:50])


# ─────────────────────────────────────────────
#  G6C — BACKGROUND CLEANUP THREADS
# ─────────────────────────────────────────────

def _job_cleanup_loop():
    """Background thread: clean up stale/expired jobs every 5 minutes (G6C)."""
    while True:
        time.sleep(300)
        try:
            cleanup_stale_jobs(jobs)
        except Exception as e:
            log.error("job_cleanup_error", error=str(e))


def _session_cleanup_loop():
    """Background thread: clean up expired sessions every 30 minutes (G5)."""
    while True:
        time.sleep(1800)
        try:
            removed = auth.cleanup_expired_sessions()
            if removed:
                log.info("expired_sessions_cleaned", count=removed)
        except Exception as e:
            log.error("session_cleanup_error", error=str(e))


# ─────────────────────────────────────────────
#  BACKGROUND CLEANUP — Start at module level
#  (gunicorn imports the module and uses `app` directly,
#   it never runs __main__, so these must start here)
# ─────────────────────────────────────────────

_cleanup_started = False

def _start_cleanup_threads():
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    threading.Thread(target=_job_cleanup_loop, daemon=True).start()
    threading.Thread(target=_session_cleanup_loop, daemon=True).start()

_start_cleanup_threads()


# ─────────────────────────────────────────────
#  MAIN (local development only)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 60)
    print("  >> AgentForge Server (with Guardrails)")
    print("=" * 60)
    print(f"  Frontend : {FRONTEND_DIR}")
    print(f"  Backend  : {BASE_DIR}")
    print(f"  Database : {auth.DB_PATH}")
    print(f"  URL      : http://localhost:{port}")
    print("  " + "-" * 37)
    print("  Guardrails Active:")
    print("    G1  Input Validation + Injection Detection")
    print("    G2  Rate Limiting (5/hr pipeline, 10/5m auth)")
    print("    G3  Code Security Scanner")
    print("    G4  Spec + Verifier Output Validation")
    print("    G5  Auth Hardening + Security Headers")
    print("    G6  Execution Limits + Auto-Expiry")
    print("    G7  Structured JSON Logging")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
