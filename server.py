"""
server.py — Flask API Server for the Agentic System Frontend

Wraps the existing backend pipeline with a REST API.
Does NOT modify any backend scripts — calls them via subprocess.

Endpoints:
    GET  /                  → serves frontend/index.html
    POST /api/generate      → starts pipeline with a prompt
    GET  /api/status/<id>   → poll current step progress
    GET  /api/result/<id>   → fetch all generated artifacts
    GET  /api/history       → returns past prompts from input.csv
"""

import os
import sys
import csv
import json
import uuid
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = BASE_DIR / "frontend"
PYTHON = sys.executable

# Force UTF-8 for subprocess so backend emoji prints don't crash on Windows
SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

# Backend scripts (untouched)
PERSPECTIVE_AGENT = BASE_DIR / "perspective_agent.py"
INPUT_EXTRACTOR   = BASE_DIR / "inputextractor.py"
AGENT_BUILD       = BASE_DIR / "agentbuild.py"
VERIFIER_AGENT    = BASE_DIR / "verifier.py"
CODE_INTERFACE    = BASE_DIR / "code_interface_agent.py"

# Artifacts
INPUT_CSV              = BASE_DIR / "input.csv"
BUILD_AGENT_OUTPUT     = BASE_DIR / "build_agent_output.json"
CONVERSATIONAL_OUTPUT  = BASE_DIR / "conversational_output.json"
FINAL_AGENT_JSON       = BASE_DIR / "final_agent.json"
GENERATED_AGENT_FOLDER = BASE_DIR / "generated_agent"
VERIFIER_RESULT        = BASE_DIR / "verifier_result.json"
OUTPUT_MD              = BASE_DIR / "output.md"

# ─────────────────────────────────────────────
#  FLASK APP
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=str(FRONTEND_DIR))
CORS(app)

# In-memory job store
jobs = {}


# ─────────────────────────────────────────────
#  STATIC FILE SERVING
# ─────────────────────────────────────────────
@app.route("/")
def serve_index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(str(FRONTEND_DIR), filename)


# ─────────────────────────────────────────────
#  SAVE INPUT TO CSV (mirrors main.py logic)
# ─────────────────────────────────────────────
def save_input_to_csv(user_input: str):
    file_exists = INPUT_CSV.exists()
    with open(INPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_input"])
        writer.writerow([datetime.now().isoformat(), user_input])


# ─────────────────────────────────────────────
#  PIPELINE RUNNER (background thread)
# ─────────────────────────────────────────────
PIPELINE_STEPS = [
    {
        "id": "perspective",
        "name": "Perspective Agent",
        "description": "Classifying input as agent-building or conversational",
        "icon": "🔍",
    },
    {
        "id": "extractor",
        "name": "Input Extractor",
        "description": "Extracting agent specifications into structured JSON",
        "icon": "📋",
    },
    {
        "id": "builder",
        "name": "Code Generator",
        "description": "Generating agent code files (agent.py, main.py, etc.)",
        "icon": "⚙️",
    },
    {
        "id": "verifier",
        "name": "Verifier Agent",
        "description": "Reviewing code correctness against specification",
        "icon": "✅",
    },
    {
        "id": "interface",
        "name": "Code Interface",
        "description": "Producing final analysis report and documentation",
        "icon": "📄",
    },
]


def run_pipeline(job_id: str, prompt: str):
    """Run the full pipeline in a background thread."""
    job = jobs[job_id]

    try:
        # Step 0: Save input
        save_input_to_csv(prompt)
        job["prompt"] = prompt

        # Clean stale outputs
        for stale in [BUILD_AGENT_OUTPUT, CONVERSATIONAL_OUTPUT,
                      FINAL_AGENT_JSON, VERIFIER_RESULT, OUTPUT_MD]:
            if stale.exists():
                stale.unlink()

        # ── Step 1: Perspective Agent ────────────────────────
        job["current_step"] = 0
        job["steps"][0]["status"] = "running"

        result = subprocess.run(
            [PYTHON, str(PERSPECTIVE_AGENT)],
            cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=180,
            env=SUBPROCESS_ENV
        )

        if result.returncode != 0:
            job["steps"][0]["status"] = "error"
            job["steps"][0]["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            job["status"] = "error"
            job["error"] = f"Perspective Agent failed: {result.stderr[-300:]}"
            return

        job["steps"][0]["status"] = "done"

        # Check route
        if CONVERSATIONAL_OUTPUT.exists():
            try:
                conv_data = json.loads(CONVERSATIONAL_OUTPUT.read_text(encoding="utf-8"))
                job["route"] = "conversational"
                job["conversational_response"] = conv_data.get("conversational_response", "")
                job["classification"] = conv_data
                # Skip remaining steps for conversational
                for i in range(1, 5):
                    job["steps"][i]["status"] = "skipped"
                job["status"] = "done"
                job["current_step"] = 5
                return
            except Exception:
                pass

        job["route"] = "agent_building"

        if BUILD_AGENT_OUTPUT.exists():
            try:
                job["classification"] = json.loads(BUILD_AGENT_OUTPUT.read_text(encoding="utf-8"))
            except Exception:
                pass

        # ── Step 2: Input Extractor ──────────────────────────
        job["current_step"] = 1
        job["steps"][1]["status"] = "running"

        result = subprocess.run(
            [PYTHON, str(INPUT_EXTRACTOR)],
            cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=300,
            input="yes\n",  # auto-confirm
            env=SUBPROCESS_ENV
        )

        if result.returncode != 0:
            job["steps"][1]["status"] = "error"
            job["steps"][1]["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            job["status"] = "error"
            job["error"] = f"Input Extractor failed: {result.stderr[-300:]}"
            return

        job["steps"][1]["status"] = "done"

        if FINAL_AGENT_JSON.exists():
            try:
                job["agent_spec"] = json.loads(FINAL_AGENT_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass

        # ── Step 3: Agent Builder ────────────────────────────
        job["current_step"] = 2
        job["steps"][2]["status"] = "running"

        result = subprocess.run(
            [PYTHON, str(AGENT_BUILD)],
            cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=300,
            env=SUBPROCESS_ENV
        )

        if result.returncode != 0:
            job["steps"][2]["status"] = "error"
            job["steps"][2]["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            job["status"] = "error"
            job["error"] = f"Agent Builder failed: {result.stderr[-300:]}"
            return

        job["steps"][2]["status"] = "done"

        # ── Step 4: Verifier ─────────────────────────────────
        job["current_step"] = 3
        job["steps"][3]["status"] = "running"

        result = subprocess.run(
            [PYTHON, str(VERIFIER_AGENT)],
            cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=180,
            env=SUBPROCESS_ENV
        )

        if result.returncode != 0:
            job["steps"][3]["status"] = "error"
            job["steps"][3]["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            # Don't fail pipeline on verifier error, continue
        else:
            job["steps"][3]["status"] = "done"

        if VERIFIER_RESULT.exists():
            try:
                job["verifier_result"] = json.loads(VERIFIER_RESULT.read_text(encoding="utf-8"))
                job["steps"][3]["status"] = "done"
            except Exception:
                pass

        # ── Step 5: Code Interface Agent ─────────────────────
        job["current_step"] = 4
        job["steps"][4]["status"] = "running"

        result = subprocess.run(
            [PYTHON, str(CODE_INTERFACE),
             "--folder", str(GENERATED_AGENT_FOLDER),
             "--output", str(OUTPUT_MD)],
            cwd=str(BASE_DIR),
            capture_output=True, text=True, timeout=300,
            env=SUBPROCESS_ENV
        )

        if result.returncode != 0:
            job["steps"][4]["status"] = "error"
            job["steps"][4]["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
        else:
            job["steps"][4]["status"] = "done"

        # ── Done ─────────────────────────────────────────────
        job["current_step"] = 5
        job["status"] = "done"

    except subprocess.TimeoutExpired:
        step_idx = job.get("current_step", 0)
        job["steps"][step_idx]["status"] = "error"
        job["steps"][step_idx]["error"] = "Step timed out"
        job["status"] = "error"
        job["error"] = "Pipeline step timed out"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


# ─────────────────────────────────────────────
#  API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    prompt = (data or {}).get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    if len(prompt) < 3:
        return jsonify({"error": "Prompt too short (min 3 chars)"}), 400

    if len(prompt) > 5000:
        return jsonify({"error": "Prompt too long (max 5000 chars)"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "prompt": prompt,
        "status": "running",
        "route": None,
        "current_step": 0,
        "steps": [
            {"id": s["id"], "name": s["name"], "description": s["description"],
             "icon": s["icon"], "status": "pending", "error": None}
            for s in PIPELINE_STEPS
        ],
        "classification": None,
        "agent_spec": None,
        "verifier_result": None,
        "conversational_response": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    thread = threading.Thread(target=run_pipeline, args=(job_id, prompt), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "route": job["route"],
        "current_step": job["current_step"],
        "steps": job["steps"],
        "error": job["error"],
    })


@app.route("/api/result/<job_id>")
def result(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result_data = {
        "id": job["id"],
        "status": job["status"],
        "route": job["route"],
        "prompt": job["prompt"],
        "classification": job["classification"],
        "agent_spec": job["agent_spec"],
        "verifier_result": job["verifier_result"],
        "conversational_response": job["conversational_response"],
        "files": {},
        "output_md": None,
    }

    # Read generated files
    if GENERATED_AGENT_FOLDER.is_dir():
        for fname in ["agent.py", "main.py", "requirements.txt", "README.md"]:
            fpath = GENERATED_AGENT_FOLDER / fname
            if fpath.exists():
                try:
                    result_data["files"][fname] = fpath.read_text(encoding="utf-8")
                except Exception:
                    result_data["files"][fname] = "[Error reading file]"

    # Read output.md
    if OUTPUT_MD.exists():
        try:
            result_data["output_md"] = OUTPUT_MD.read_text(encoding="utf-8")
        except Exception:
            pass

    return jsonify(result_data)


@app.route("/api/history")
def history():
    entries = []
    if INPUT_CSV.exists():
        try:
            with open(INPUT_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append({
                        "timestamp": row.get("timestamp", ""),
                        "prompt": row.get("user_input", ""),
                    })
        except Exception:
            pass

    # Return most recent first
    entries.reverse()
    return jsonify(entries[:50])


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  >> Agentic System Frontend Server")
    print("=" * 60)
    print(f"  Frontend : {FRONTEND_DIR}")
    print(f"  Backend  : {BASE_DIR}")
    print(f"  URL      : http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=True)
