"""
main.py — Pipeline Orchestrator

Runs the full agent-generation pipeline in order:

  Step 0 │ Save user input       │ text input        → input.csv
  Step 1 │ perspective_agent.py  │ text input        → build_agent_output.json
  Step 2 │ inputextractor.py     │ build_agent_output.json → final_agent.json
  Step 3 │ agentbuild.py         │ final_agent.json  → generated_agent/
  Step 4 │ verifier.py           │ generated_agent/  → verifier_result.json

Usage:
    python main.py
    python main.py --input "Build me a web scraping agent"
    python main.py --input-file prompt.txt
    python main.py --skip-on-failure   # continue pipeline even if a step fails
"""

import os
import sys
import csv
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Load local environment (e.g., GROQ_API_KEY in .env) for subprocess steps.
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR               = Path(__file__).parent.resolve()

# Intermediate & final artifacts
INPUT_CSV              = BASE_DIR / "input.csv"
BUILD_AGENT_OUTPUT     = BASE_DIR / "build_agent_output.json"
FINAL_AGENT_JSON       = BASE_DIR / "final_agent.json"
GENERATED_AGENT_FOLDER = BASE_DIR / "generated_agent"
VERIFIER_RESULT        = BASE_DIR / "verifier_result.json"

# Agent scripts
PERSPECTIVE_AGENT      = BASE_DIR / "perspective_agent.py"
INPUT_EXTRACTOR        = BASE_DIR / "inputextractor.py"
AGENT_BUILD            = BASE_DIR / "agentbuild.py"
VERIFIER_AGENT         = BASE_DIR / "verifier.py"

PYTHON                 = sys.executable


# ─────────────────────────────────────────────────────────────────────────────
# PRETTY PRINTING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"


def banner():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗
║          Agent Generation Pipeline — main.py         ║
╚══════════════════════════════════════════════════════╝{RESET}
""")


def step_header(n: int, total: int, title: str, script: str):
    bar = "─" * 54
    print(f"\n{BOLD}{CYAN}┌{bar}┐{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  Step {n}/{total}: {BOLD}{title}{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  Script : {DIM}{script}{RESET}")
    print(f"{BOLD}{CYAN}└{bar}┘{RESET}")


def ok(msg: str):
    print(f"  {GREEN}✓{RESET}  {msg}")


def warn(msg: str):
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def err(msg: str):
    print(f"  {RED}✗{RESET}  {msg}")


def info(msg: str):
    print(f"  {CYAN}→{RESET}  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# CSV INPUT LOGGER
# ─────────────────────────────────────────────────────────────────────────────

def save_input_to_csv(user_input: str):
    """
    Appends the user input to input.csv with a timestamp.
    Creates the file with a header row if it does not exist yet.
    """
    file_exists = INPUT_CSV.exists()

    with open(INPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_input"])   # header on first run
        writer.writerow([datetime.now().isoformat(), user_input])

    ok(f"User input saved → {INPUT_CSV.name}")


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def validate_scripts():
    """Ensure all agent scripts exist before starting."""
    missing = []
    for script in [PERSPECTIVE_AGENT, INPUT_EXTRACTOR, AGENT_BUILD, VERIFIER_AGENT]:
        if not script.exists():
            missing.append(str(script))
    if missing:
        err("The following required scripts were NOT found:")
        for m in missing:
            print(f"        {RED}•{RESET} {m}")
        print()
        sys.exit(1)
    ok("All pipeline scripts found.")


def assert_file_exists(path: Path, label: str, skip: bool) -> bool:
    if path.exists() and path.stat().st_size > 0:
        ok(f"Output produced: {path.name}  ({path.stat().st_size:,} bytes)")
        return True
    else:
        msg = f"Expected output not found or empty: {path}"
        if skip:
            warn(msg + "  — skipping to next step.")
            return False
        else:
            err(msg)
            sys.exit(1)


def assert_folder_exists(path: Path, label: str, skip: bool) -> bool:
    if path.is_dir() and any(path.iterdir()):
        files = list(path.iterdir())
        ok(f"Folder produced: {path.name}/  ({len(files)} file(s) inside)")
        return True
    else:
        msg = f"Expected folder not found or empty: {path}"
        if skip:
            warn(msg + "  — skipping to next step.")
            return False
        else:
            err(msg)
            sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# STEP RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_step(
    cmd: list,
    step_name: str,
    skip_on_failure: bool,
    env: dict | None = None,
) -> bool:
    info(f"Running: {' '.join(str(c) for c in cmd)}")
    start = time.time()

    merged_env = {**os.environ, **(env or {})}

    try:
        result = subprocess.run(
            [str(c) for c in cmd],
            cwd=str(BASE_DIR),
            env=merged_env,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            ok(f"{step_name} completed in {elapsed:.1f}s")
            return True
        else:
            msg = f"{step_name} exited with code {result.returncode}"
            if skip_on_failure:
                warn(msg + "  — continuing pipeline.")
                return False
            else:
                err(msg)
                sys.exit(result.returncode)

    except FileNotFoundError as e:
        msg = f"Script not found: {e}"
        if skip_on_failure:
            warn(msg)
            return False
        else:
            err(msg)
            sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────────────────────────────────────

def step1_perspective_agent(user_input: str, skip: bool) -> bool:
    step_header(1, 4, "Perspective Agent", PERSPECTIVE_AGENT.name)
    info(f"User input: \"{user_input[:80]}{'...' if len(user_input) > 80 else ''}\"")
    info(f"Expected output → {BUILD_AGENT_OUTPUT.name}")

    # Delete stale outputs from previous run so we can detect what was actually produced
    for stale in [BUILD_AGENT_OUTPUT, BASE_DIR / "conversational_output.json"]:
        if stale.exists():
            stale.unlink()

    success = run_step(
        cmd=[PYTHON, PERSPECTIVE_AGENT, "--input", user_input,
             "--output", str(BUILD_AGENT_OUTPUT)],
        step_name="perspective_agent",
        skip_on_failure=skip,
    )
    if not success:
        return False

    # Accept either output file as a valid result
    conv_out = BASE_DIR / "conversational_output.json"
    if conv_out.exists():
        ok(f"Output produced: conversational_output.json  ({conv_out.stat().st_size:,} bytes)")
        return True
    return assert_file_exists(BUILD_AGENT_OUTPUT, "build_agent_output.json", skip)


def step2_input_extractor(skip: bool) -> bool:
    step_header(2, 4, "Input Extractor", INPUT_EXTRACTOR.name)
    info(f"Reading  ← {BUILD_AGENT_OUTPUT.name}")
    info(f"Expected output → {FINAL_AGENT_JSON.name}")

    success = run_step(
        cmd=[PYTHON, INPUT_EXTRACTOR,
             "--input",  str(BUILD_AGENT_OUTPUT),
             "--output", str(FINAL_AGENT_JSON)],
        step_name="inputextractor",
        skip_on_failure=skip,
    )
    if not success:
        return False
    return assert_file_exists(FINAL_AGENT_JSON, "final_agent.json", skip)


def step3_agent_build(skip: bool) -> bool:
    """
    agentbuild.py reads final_agent.json directly — no CLI args needed.
    Writes output to generated_agent/ folder automatically.
    """
    step_header(3, 4, "Agent Builder", AGENT_BUILD.name)
    info(f"Reading  ← {FINAL_AGENT_JSON.name}")
    info(f"Expected output → {GENERATED_AGENT_FOLDER.name}/")

    success = run_step(
        cmd=[PYTHON, AGENT_BUILD],          # no extra args — agentbuild reads final_agent.json itself
        step_name="agentbuild",
        skip_on_failure=skip,
    )
    if not success:
        return False
    return assert_folder_exists(GENERATED_AGENT_FOLDER, "generated_agent/", skip)


def step4_verifier_agent(skip: bool) -> bool:
    """
    verifier.py reads generated_agent/ and writes verifier_result.json — no CLI args needed.
    Uses Groq AI review only (no difflib).
    """
    step_header(4, 4, "Verifier Agent", VERIFIER_AGENT.name)
    info(f"Reading  ← {GENERATED_AGENT_FOLDER.name}/")
    info(f"Expected output → {VERIFIER_RESULT.name}")

    success = run_step(
        cmd=[PYTHON, VERIFIER_AGENT],       # no extra args — verifier.py uses hardcoded paths
        step_name="verifier",
        skip_on_failure=skip,
    )
    if not success:
        return False

    verified = assert_file_exists(VERIFIER_RESULT, "verifier_result.json", skip)
    if verified:
        _print_verifier_summary()
    return verified


def _print_verifier_summary():
    """Pretty-print key fields from verifier_result.json."""
    try:
        data       = json.loads(VERIFIER_RESULT.read_text(encoding="utf-8"))
        status     = data.get("overall_status", "unknown")
        score      = data.get("correctness_score")
        band       = data.get("correctness_band")
        ai_review  = (data.get("layer4_llm") or {}).get("details", {})
        issues     = ai_review.get("issues", [])
        summary    = ai_review.get("summary", data.get("delivery_notes", ""))

        color = GREEN if str(status).upper() == "PASS" else YELLOW

        print(f"\n  {BOLD}Verifier Summary (Groq AI Review){RESET}")
        print(f"  Status  : {color}{status}{RESET}")
        if score is not None:
            print(f"  Score   : {score}%")
        if band:
            print(f"  Band    : {band}")
        if summary:
            print(f"  Verdict : {summary}")
        if issues:
            print(f"  Issues  : {len(issues)} found")
            for i, issue in enumerate(issues[:5], 1):
                print(f"    {i}. {issue}")
    except Exception:
        pass

def check_route_from_output() -> str:
    """
    Check which file perspective_agent actually produced this run.
    conversational_output.json  → code_interface
    build_agent_output.json     → json_extractor
    """
    conv_path  = BASE_DIR / "conversational_output.json"
    build_path = BUILD_AGENT_OUTPUT

    if conv_path.exists():
        # If both exist, use whichever is newer (current run)
        if not build_path.exists() or conv_path.stat().st_mtime >= build_path.stat().st_mtime:
            return "code_interface"

    try:
        data = json.loads(build_path.read_text(encoding="utf-8"))
        return data.get("route", "json_extractor")
    except Exception:
        return "json_extractor"


def show_conversational_response():
    """Print the conversational response from conversational_output.json."""
    conv_path = BASE_DIR / "conversational_output.json"
    try:
        data     = json.loads(conv_path.read_text(encoding="utf-8"))
        response = data.get("conversational_response", "")
        print(f"\n{BOLD}{CYAN}── Conversational Response ──{RESET}\n")
        print(f"  {response}\n")
        print(f"{DIM}{'─' * 56}{RESET}\n")
    except Exception:
        warn("Could not read conversational_output.json")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(results: dict, elapsed_total: float):
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗")
    print(f"║                   Pipeline Summary                  ║")
    print(f"╚══════════════════════════════════════════════════════╝{RESET}\n")

    icons = {True: f"{GREEN}✓ PASS{RESET}", False: f"{RED}✗ FAIL{RESET}"}
    rows = [
        ("Step 1 │ Perspective Agent",    "build_agent_output.json"),
        ("Step 2 │ Input Extractor",       "final_agent.json"),
        ("Step 3 │ Agent Builder",         "generated_agent/"),
        ("Step 4 │ Verifier Agent",        "verifier_result.json"),
    ]
    for (label, artifact), passed in zip(rows, results.values()):
        status = icons[passed]
        print(f"  {status}  {label}")
        if passed:
            print(f"           {DIM}→ {artifact}{RESET}")

    overall = all(results.values())
    color   = GREEN if overall else YELLOW
    print(f"\n  {BOLD}Overall : {color}{'SUCCESS' if overall else 'PARTIAL'}{RESET}")
    print(f"  {BOLD}Time    : {elapsed_total:.1f}s{RESET}")

    if overall:
        print(f"\n  {GREEN}All outputs are ready.{RESET}")
        print(f"  Open {BOLD}generated_agent/README.md{RESET} for run instructions.\n")
    else:
        print(f"\n  {YELLOW}Some steps did not complete — check logs above.{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orchestrates the full agent-generation pipeline."
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--input", "-i",
        type=str,
        help="Text prompt describing the agent to build.",
    )
    input_group.add_argument(
        "--input-file", "-f",
        type=str,
        help="Path to a .txt file containing the prompt.",
    )

    parser.add_argument(
        "--skip-on-failure",
        action="store_true",
        default=False,
        help="Continue to the next step even if a step fails.",
    )

    parser.add_argument(
        "--start-from",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="Resume pipeline from a specific step (1–4).",
    )

    return parser.parse_args()


def resolve_user_input(args: argparse.Namespace) -> str:
    """Return the user prompt string from args or interactive input."""
    if args.input:
        return args.input.strip()

    if args.input_file:
        p = Path(args.input_file)
        if not p.exists():
            err(f"Input file not found: {p}")
            sys.exit(1)
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            err("Input file is empty.")
            sys.exit(1)
        return text

    # Interactive fallback
    print(f"{BOLD}Enter your agent prompt{RESET} (press Enter twice when done):\n")
    lines = []
    try:
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    text = "\n".join(lines).strip()
    if not text:
        err("No input provided.")
        sys.exit(1)
    return text


def main():
    banner()
    args = parse_args()

    # ── Pre-flight checks ────────────────────────────────────────────────────
    print(f"{BOLD}[Pre-flight]{RESET}")
    validate_scripts()
    print(f"  Working directory : {BASE_DIR}")
    print(f"  Python            : {PYTHON}")
    print(f"  Start from step   : {args.start_from}")
    print(f"  Skip on failure   : {args.skip_on_failure}")

    skip = args.skip_on_failure

    # ── Main loop — repeats if route is conversational ───────────────────────
    while True:
        # ── Resolve + save user input ────────────────────────────────────────
        user_input = ""
        if args.start_from == 1:
            user_input = resolve_user_input(args)
            save_input_to_csv(user_input)
            # After first run, clear --input so the loop prompts interactively
            args.input      = None
            args.input_file = None

        results: dict      = {}
        pipeline_start     = time.time()

        # ── Step 1 ───────────────────────────────────────────────────────────
        if args.start_from <= 1:
            results["step1"] = step1_perspective_agent(user_input, skip)
        else:
            results["step1"] = True
            info("Skipping Step 1 (--start-from requested).")

        # ── Check route ───────────────────────────────────────────────────────
        if results["step1"] and args.start_from <= 1:
            route = check_route_from_output()
            if route == "code_interface":
                show_conversational_response()
                info("Conversational response shown. Enter a new prompt to continue.\n")
                args.start_from = 1   # force restart from step 1
                continue              # ← loop back to user input

        # ── Step 2 ───────────────────────────────────────────────────────────
        if args.start_from <= 2:
            results["step2"] = step2_input_extractor(skip)
        else:
            results["step2"] = True
            info("Skipping Step 2 (--start-from requested).")

        # ── Step 3 ───────────────────────────────────────────────────────────
        if args.start_from <= 3:
            results["step3"] = step3_agent_build(skip)
        else:
            results["step3"] = True
            info("Skipping Step 3 (--start-from requested).")

        # ── Step 4 ───────────────────────────────────────────────────────────
        if args.start_from <= 4:
            results["step4"] = step4_verifier_agent(skip)
        else:
            results["step4"] = True
            info("Skipping Step 4 (--start-from requested).")

        # ── Summary ───────────────────────────────────────────────────────────
        total_elapsed = time.time() - pipeline_start
        print_summary(results, total_elapsed)
        break   # ← agent building done, exit loop

    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()