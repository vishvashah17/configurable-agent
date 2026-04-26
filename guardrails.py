"""
guardrails.py — AgentForge Deployment Guardrails
==================================================
Provides enforcement boundaries at every layer of the system:

  G1  —  Input Validation & Prompt Injection Detection
  G2  —  Per-User Rate Limiting & Concurrent Job Limits
  G4  —  LLM Output / Schema Validation
  G7  —  Structured JSON Logging

Usage:
    from guardrails import (
        validate_prompt,
        detect_prompt_injection,
        PIPELINE_LIMITER,
        API_LIMITER,
        validate_agent_spec,
        validate_verifier_result,
        log,
    )
"""

import json as _json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from groq_utils import groq_chat_json

# ─────────────────────────────────────────────
#  G7 — STRUCTURED JSON LOGGER
# ─────────────────────────────────────────────

class StructuredLogger:
    """
    Emits structured JSON log lines to stdout.

    Provides consistent, machine-parseable logs for every guardrail
    event, pipeline action, and security detection across the system.
    """

    def __init__(self, name: str = "agentforge"):
        self._name = name

    def _emit(self, level: str, event: str, **kwargs) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": self._name,
            "level": level,
            "event": event,
        }
        record.update(kwargs)
        try:
            print(_json.dumps(record, default=str), flush=True)
        except Exception:
            print(f"[{level}] {event}", flush=True)

    def info(self, event: str, **kwargs) -> None:
        self._emit("INFO", event, **kwargs)

    def warn(self, event: str, **kwargs) -> None:
        self._emit("WARN", event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._emit("ERROR", event, **kwargs)

    def security(self, event: str, **kwargs) -> None:
        """Security-specific log level for audit trail."""
        self._emit("SECURITY", event, **kwargs)


log = StructuredLogger("agentforge")


# ─────────────────────────────────────────────
#  G1A — INPUT VALIDATION
# ─────────────────────────────────────────────

# Minimum meaningful prompt length (increased from 3 for deployment)
MIN_PROMPT_LENGTH = 10
MAX_PROMPT_LENGTH = 5000
MAX_URL_COUNT = 5


def validate_prompt(prompt: str) -> tuple[bool, str]:
    """
    Validate and sanitize user prompt before any processing.

    Returns:
        (is_valid, cleaned_prompt_or_error_message)
    """
    if not isinstance(prompt, str):
        log.warn("input_validation_fail", reason="non_string_input")
        return False, "Input must be a string."

    # 1. Strip and normalize unicode (NFKC normalizes compatibility characters)
    prompt = unicodedata.normalize("NFKC", prompt.strip())

    # 2. Length checks
    if len(prompt) < MIN_PROMPT_LENGTH:
        return False, f"Prompt too short (min {MIN_PROMPT_LENGTH} chars). Describe the agent you want to build."
    if len(prompt) > MAX_PROMPT_LENGTH:
        return False, f"Prompt exceeds {MAX_PROMPT_LENGTH} characters."

    # 3. Null bytes / control characters (common injection vector)
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', prompt):
        log.security("control_char_detected", prompt_length=len(prompt))
        return False, "Invalid characters detected."

    # 4. Repeated character spam (aaaaaaa... or !!!!!...)
    if re.search(r'(.)\1{30,}', prompt):
        log.security("char_spam_detected", prompt_length=len(prompt))
        return False, "Prompt contains invalid repeated content."

    # 5. URL density check (prompt injection via URLs)
    urls = re.findall(r'https?://', prompt)
    if len(urls) > MAX_URL_COUNT:
        log.security("url_density_exceeded", url_count=len(urls))
        return False, f"Too many URLs in prompt (max {MAX_URL_COUNT})."

    # 6. All-whitespace after strip
    if not prompt:
        return False, "Prompt cannot be empty."

    return True, prompt


# ─────────────────────────────────────────────
#  G1B — PROMPT INJECTION DETECTION
# ─────────────────────────────────────────────

# Compiled once at import for performance
INJECTION_PATTERNS = [
    # System prompt overrides
    re.compile(r"ignore (all |previous |above |prior )?instructions", re.I),
    re.compile(r"disregard (your |all )?instructions", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"new persona", re.I),
    re.compile(r"forget (everything|all|your instructions)", re.I),
    re.compile(r"system\s*prompt\s*:", re.I),
    re.compile(r"your (real |true )?instructions are", re.I),

    # Role hijacking
    re.compile(r"act as (a |an )?(unrestricted|evil|jailbreak|DAN)", re.I),
    re.compile(r"pretend you (are|have no)", re.I),
    re.compile(r"you have no restrictions", re.I),
    re.compile(r"developer mode", re.I),

    # Data exfiltration attempts
    re.compile(r"repeat (everything|your (system|instructions))", re.I),
    re.compile(r"print your (system prompt|instructions)", re.I),
    re.compile(r"output your (full |entire )?prompt", re.I),

    # Code injection in prompt
    re.compile(r"exec\s*\(", re.I),
    re.compile(r"eval\s*\(", re.I),
    re.compile(r"__import__", re.I),
    re.compile(r"subprocess\.run", re.I),
    re.compile(r"os\.system", re.I),
]


def detect_prompt_injection(prompt: str) -> tuple[bool, str]:
    """
    Scan prompt for known injection patterns.

    Returns:
        (is_injection_detected, matched_pattern_label_or_empty)
    """
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(prompt)
        if match:
            matched_text = match.group()
            log.security(
                "prompt_injection_detected",
                matched_pattern=matched_text[:60],
                prompt_length=len(prompt),
            )
            return True, "Prompt flagged for policy violation."
    return False, ""


# ─────────────────────────────────────────────
#  G1C — OPTIONAL LLM CONTENT POLICY CHECK
# ─────────────────────────────────────────────

CONTENT_GUARD_PROMPT = """\
You are a strict content moderation classifier.

Return ONLY valid JSON:
{
  "safe": true/false,
  "reason": "one short line if unsafe; empty string if safe",
  "category": "safe | malware | adult | violence | illegal | data_theft | other"
}

Prompt to classify:
{prompt}
"""


def llm_content_check(prompt: str, enabled: bool = False) -> tuple[bool, str]:
    """
    Optional low-cost moderation call for borderline prompts.
    Disabled by default to avoid extra latency/cost.
    """
    if not enabled:
        return True, ""
    try:
        result = groq_chat_json(
            system="You are a strict content moderator. Return only JSON.",
            user=CONTENT_GUARD_PROMPT.format(prompt=prompt),
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=120,
        )
        if not bool(result.get("safe", True)):
            reason = str(result.get("reason", "") or "Content policy violation.")
            category = str(result.get("category", "other"))
            log.security("content_policy_blocked", category=category, reason=reason[:120])
            return False, reason
        return True, ""
    except Exception as e:
        # Fail-open for availability, but log strongly.
        log.warn("content_policy_check_failed", error=str(e))
        return True, ""


# ─────────────────────────────────────────────
#  G2 — RATE LIMITING (Per-User, Sliding Window)
# ─────────────────────────────────────────────

class RateLimiter:
    """
    Thread-safe sliding-window rate limiter.

    Tracks request timestamps per user over a rolling window.
    Old entries are pruned on each call.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._log: dict[int, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, user_id: int) -> tuple[bool, int]:
        """
        Check if a request from user_id is allowed.

        Returns:
            (allowed, seconds_until_reset)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Prune expired entries
            self._log[user_id] = [t for t in self._log[user_id] if t > cutoff]

            if len(self._log[user_id]) >= self.max_requests:
                oldest = self._log[user_id][0]
                wait = int(self.window_seconds - (now - oldest)) + 1
                log.warn(
                    "rate_limit_hit",
                    user_id=user_id,
                    limit=self.max_requests,
                    window_seconds=self.window_seconds,
                    retry_after=wait,
                )
                return False, wait

            self._log[user_id].append(now)
            return True, 0

    def reset(self, user_id: int) -> None:
        """Clear all entries for a user (e.g., on admin reset)."""
        with self._lock:
            self._log.pop(user_id, None)


# Pre-configured limiters for deployment
PIPELINE_LIMITER = RateLimiter(max_requests=5, window_seconds=3600)     # 5 pipeline runs / hour
API_LIMITER = RateLimiter(max_requests=30, window_seconds=60)           # 30 API calls / minute
AUTH_LIMITER = RateLimiter(max_requests=10, window_seconds=300)         # 10 auth attempts / 5 min


# ─────────────────────────────────────────────
#  G2B — CONCURRENT JOB LIMITS
# ─────────────────────────────────────────────

MAX_CONCURRENT_JOBS = 5          # Server-wide cap
MAX_JOBS_PER_USER = 2            # Per-user cap


def user_has_active_job(jobs: dict, user_id: str | int) -> bool:
    """Check if a user already has a running or awaiting job."""
    user_str = str(user_id)
    return any(
        str(j.get("user_id", j.get("user", ""))) == user_str
        and j["status"] in ("running", "awaiting_confirmation")
        for j in jobs.values()
    )


def count_active_jobs(jobs: dict) -> int:
    """Count all jobs with active status across the server."""
    return sum(
        1 for j in jobs.values()
        if j["status"] in ("running", "awaiting_confirmation")
    )


# ─────────────────────────────────────────────
#  G4A — AGENT SPEC SCHEMA VALIDATION
# ─────────────────────────────────────────────

REQUIRED_AGENT_FIELDS: dict[str, type] = {
    "agent_name": str,
    "primary_purpose": str,
    "capabilities": list,
    "language": str,
}

# Frameworks mistakenly set as language
FRAMEWORKS_NOT_LANGUAGES = {
    "langchain", "fastapi", "flask", "django", "react", "vue",
    "angular", "express", "spring", "rails", "laravel",
    "crewai", "autogen", "streamlit", "gradio",
}


def validate_agent_spec(spec: dict) -> tuple[bool, list[str]]:
    """
    Validate the final_agent.json schema before code generation.

    Returns:
        (is_valid, list_of_error_messages)
    """
    if not isinstance(spec, dict):
        return False, ["Agent spec must be a JSON object."]

    errors: list[str] = []

    # Required fields
    for field, expected_type in REQUIRED_AGENT_FIELDS.items():
        val = spec.get(field)
        if val is None or val == "" or val == []:
            errors.append(f"Required field '{field}' is missing or empty.")
        elif not isinstance(val, expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, "
                f"got {type(val).__name__}."
            )

    # Capabilities must not be empty
    caps = spec.get("capabilities")
    if isinstance(caps, list) and len(caps) == 0:
        errors.append("Agent must have at least one capability defined.")

    # Language must be a real programming language, not a framework
    lang = (spec.get("language") or "").lower().strip()
    if lang in FRAMEWORKS_NOT_LANGUAGES:
        errors.append(
            f"'{spec.get('language')}' is a framework, not a language. "
            f"Fix the 'language' field."
        )

    # Agent name sanity
    name = spec.get("agent_name", "")
    if isinstance(name, str) and len(name) > 80:
        errors.append("Agent name too long (max 80 characters).")

    if errors:
        log.warn("agent_spec_validation_fail", error_count=len(errors), errors=errors)

    return len(errors) == 0, errors


# ─────────────────────────────────────────────
#  G4B — VERIFIER OUTPUT VALIDATION
# ─────────────────────────────────────────────

def validate_verifier_result(result: dict) -> tuple[bool, str]:
    """
    Validate the JSON structure returned by verifier.py's LLM call
    before trusting the score.

    Returns:
        (is_valid, error_message_or_empty)
    """
    if not isinstance(result, dict):
        return False, "Verifier result must be a JSON object."

    score = result.get("correctness_percentage")
    if not isinstance(score, (int, float)):
        return False, f"correctness_percentage must be a number, got {type(score).__name__}."

    if not (0 <= score <= 100):
        return False, f"correctness_percentage out of range: {score} (must be 0–100)."

    required_keys = [
        "implemented_correctly",
        "not_implemented",
        "summary",
    ]
    missing = [k for k in required_keys if k not in result]
    if missing:
        return False, f"Missing required keys: {missing}"

    # Ensure list fields are actually lists
    for key in ["implemented_correctly", "implemented_partially", "not_implemented",
                 "hallucinated_features", "security_issues", "issues"]:
        val = result.get(key)
        if val is not None and not isinstance(val, list):
            return False, f"'{key}' must be a list, got {type(val).__name__}."

    return True, ""


# ─────────────────────────────────────────────
#  G6C — JOB AUTO-EXPIRY (Stale Job Cleanup)
# ─────────────────────────────────────────────

# Confirmation timeout (seconds) — jobs stuck in awaiting_confirmation
CONFIRMATION_TIMEOUT = 1800     # 30 minutes
# Completed job retention (seconds) — clean up old done/error jobs
COMPLETED_JOB_RETENTION = 7200  # 2 hours


def cleanup_stale_jobs(jobs: dict) -> int:
    """
    Mark expired awaiting_confirmation jobs as error.
    Remove old completed/errored jobs from memory.

    Called by a daemon thread in server.py every 5 minutes.

    Returns:
        Number of jobs cleaned up.
    """
    now = datetime.now()
    cleaned = 0

    stale_ids = []
    expired_ids = []

    for jid, j in jobs.items():
        created = j.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created)
        except (ValueError, TypeError):
            continue

        age_seconds = (now - created_dt).total_seconds()

        # Expire unconfirmed jobs
        if j["status"] == "awaiting_confirmation" and age_seconds > CONFIRMATION_TIMEOUT:
            stale_ids.append(jid)

        # Prune old completed jobs from memory
        if j["status"] in ("done", "error") and age_seconds > COMPLETED_JOB_RETENTION:
            expired_ids.append(jid)

    for jid in stale_ids:
        jobs[jid]["status"] = "error"
        jobs[jid]["error"] = "Confirmation timeout — job expired after 30 minutes."
        log.warn("job_confirmation_timeout", job_id=jid)
        cleaned += 1

    for jid in expired_ids:
        jobs.pop(jid, None)
        cleaned += 1

    if cleaned:
        log.info("stale_jobs_cleaned", count=cleaned, active_remaining=len(jobs))

    return cleaned
