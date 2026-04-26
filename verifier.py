"""
verifier.py — Multi-Layer Agent Code Verifier
==============================================
Layer 1 : AST Syntax Check         (instant, no LLM)
Layer 2 : Spec Compliance Check    (rule-based AST walk, no LLM)
Layer 3 : Groq Semantic Review     (LLM, improved prompt)

Final score = weighted composite of all three layers.
"""

import ast
import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

THRESHOLD    = 60
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL        = "llama-3.3-70b-versatile"

# Weights must sum to 100
WEIGHTS = {
    "syntax":     15,   # Layer 1
    "compliance": 30,   # Layer 2
    "llm":        55,   # Layer 3
}


# ─────────────────────────────────────────────
#  FILE HELPERS
# ─────────────────────────────────────────────

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_json(data: dict) -> str:
    return json.dumps(data, indent=2)


# ─────────────────────────────────────────────
#  LAYER 1 — AST SYNTAX CHECK
# ─────────────────────────────────────────────

def layer1_syntax(agent_code: str, main_code: str) -> dict:
    """
    Parses both files with ast.parse().
    Catches SyntaxErrors before wasting LLM tokens.
    Score: 100 if both pass, 50 if one fails, 0 if both fail.
    """
    results = {}
    passed = 0

    for name, code in [("agent.py", agent_code), ("main.py", main_code)]:
        try:
            ast.parse(code)
            results[name] = {"status": "PASS"}
            passed += 1
        except SyntaxError as e:
            results[name] = {
                "status": "FAIL",
                "error": str(e),
                "line":  e.lineno,
            }

    score = (passed / 2) * 100
    return {
        "score":   int(score),
        "details": results,
        "passed":  passed == 2,
    }


# ─────────────────────────────────────────────
#  LAYER 2 — SPEC COMPLIANCE CHECK (rule-based)
# ─────────────────────────────────────────────

def _ast_names(code: str) -> dict:
    """Extract class names, function names, and imports from source."""
    tree = ast.parse(code)
    return {
        "classes":   [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)],
        "functions": [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      or isinstance(n, ast.AsyncFunctionDef)],
        "imports":   [
            alias.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for alias in (n.names if isinstance(n, ast.Import) else
                          [type("A", (), {"name": n.module or ""})()])
        ],
        "raw_text":  code.lower(),
    }


def layer2_compliance(agent_code: str, main_code: str, spec: dict) -> dict:
    """
    Deterministic checks of the generated code against final_agent.json.
    No LLM involved — pure AST + string analysis.
    """
    checks   = {}
    passed   = 0
    total    = 0

    try:
        agent_names = _ast_names(agent_code)
        main_names  = _ast_names(main_code)
        combined_text = agent_names["raw_text"] + main_names["raw_text"]
    except SyntaxError:
        # Layer 1 already caught this; skip layer 2 gracefully
        return {"score": 0, "details": {"error": "Skipped — syntax error in Layer 1"}, "passed": False}

    def record(key: str, result: bool, note: str = ""):
        nonlocal passed, total
        total  += 1
        passed += int(result)
        checks[key] = {"passed": result, "note": note}

    # ── 1. Agent class exists ──────────────────────────────────────────────
    agent_name = (spec.get("agent_name") or "Agent").replace(" ", "")
    class_found = any(
        agent_name.lower() in c.lower() or "agent" in c.lower()
        for c in agent_names["classes"]
    )
    record("agent_class_exists", class_found,
           f"Looking for class containing '{agent_name}' or 'agent'")

    # ── 2. Framework imported ──────────────────────────────────────────────
    framework = (spec.get("framework") or "").lower()
    if framework and framework not in ("none", "n/a", ""):
        fw_found = any(framework in imp.lower() for imp in agent_names["imports"]) \
                   or framework in combined_text
        record("framework_imported", fw_found, f"Expected framework: {framework}")

    # ── 3. Capabilities covered ───────────────────────────────────────────
    capabilities = spec.get("capabilities") or []
    for cap in capabilities:
        keywords = cap.lower().replace("-", " ").replace("_", " ").split()
        # At least one keyword from the capability must appear in code
        found = any(kw in combined_text for kw in keywords if len(kw) > 3)
        record(f"capability_{cap[:40]}", found, f"Keyword search for: {keywords}")

    # ── 4. Language matches ───────────────────────────────────────────────
    lang = (spec.get("language") or "python").lower()
    if lang == "python":
        record("language_is_python", True, "Python files confirmed by their existence")
    else:
        record("language_match", lang in combined_text,
               f"Expected language hints for: {lang}")

    # ── 5. External APIs referenced ───────────────────────────────────────
    ext_apis = spec.get("external_apis") or spec.get("api_integrations") or []
    for api in ext_apis:
        api_kw = api.lower().replace(" ", "").replace("-", "")
        found  = api_kw in combined_text or api.lower() in combined_text
        record(f"api_{api[:30]}", found, f"Looking for API reference: {api}")

    # ── 6. main.py has entry-point ────────────────────────────────────────
    has_main = "__main__" in main_names["raw_text"] or \
               any("main" in fn.lower() for fn in main_names["functions"])
    record("entrypoint_exists", has_main, "main.py should call/define main or use __main__")

    # ── 7. No obvious placeholder text ───────────────────────────────────
    placeholders = ["todo", "fixme", "pass  #", "raise notimplementederror", "your_api_key"]
    found_placeholders = [p for p in placeholders if p in combined_text]
    record("no_placeholders", len(found_placeholders) == 0,
           f"Found placeholders: {found_placeholders}" if found_placeholders else "")

    score = int((passed / total) * 100) if total > 0 else 0
    return {
        "score":   score,
        "details": checks,
        "passed":  score >= 60,
        "summary": f"{passed}/{total} checks passed",
    }


# ─────────────────────────────────────────────
#  LAYER 3 — GROQ SEMANTIC REVIEW
# ─────────────────────────────────────────────

SYSTEM_VERIFIER = """\
You are a strict senior Python code auditor. Evaluate whether the generated code
correctly implements the given agent specification.

Respond with ONLY a valid JSON object — no markdown, no prose, no fences.

Required keys (do not add or remove any):
{
  "correctness_percentage":    <integer 0-100>,
  "implemented_correctly":     ["list of spec items correctly implemented"],
  "implemented_partially":     ["list of spec items partially implemented"],
  "not_implemented":           ["list of spec items missing entirely"],
  "hallucinated_features":     ["features present in code but NOT in spec"],
  "security_issues":           ["hardcoded secrets, unsafe eval/exec, subprocess shell=True, etc."],
  "issues":                    ["other specific problems found"],
  "summary":                   "one sentence overall verdict"
}

Scoring guide:
- 90-100 : All spec items implemented, no major issues
- 70-89  : Most items implemented, minor gaps
- 50-69  : Core functionality present but significant gaps
- 30-49  : Partial implementation, major features missing
- 0-29   : Does not implement the specification
"""


def layer3_llm(spec_json: str, agent_code: str, main_code: str) -> dict:
    """
    Sends spec + code to Groq for semantic review.
    Returns structured review dict.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set. Add it to your .env file.")

    client = Groq(api_key=GROQ_API_KEY)

    user_prompt = f"""\
=== AGENT SPECIFICATION (JSON) ===
{spec_json}

=== agent.py ===
{agent_code}

=== main.py ===
{main_code}

Evaluate the code against the specification strictly.
Return ONLY the JSON object described in your system instructions.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_VERIFIER},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=1200,
    )

    raw = (response.choices[0].message.content or "").strip()
    review = _safe_parse_llm_json(raw)
    score  = review.get("correctness_percentage", 0)
    return {
        "score":   int(score) if isinstance(score, (int, float)) else 0,
        "details": review,
        "passed":  isinstance(score, (int, float)) and score >= THRESHOLD,
    }


def _safe_parse_llm_json(raw: str) -> dict:
    if not raw:
        return {"correctness_percentage": 0, "issues": ["Empty LLM response"], "summary": "Empty response"}
    txt = raw.strip()
    if txt.startswith("```"):
        parts = txt.split("```")
        txt = parts[1] if len(parts) > 1 else txt
        txt = txt[4:].strip() if txt.lower().startswith("json") else txt.strip()
    try:
        return json.loads(txt)
    except Exception:
        # best-effort object extraction
        import re
        m = re.search(r"\{[\s\S]*\}", txt)
        if m:
            candidate = re.sub(r",\s*([}\]])", r"\1", m.group(0))
            try:
                return json.loads(candidate)
            except Exception:
                pass
    return {
        "correctness_percentage": 0,
        "implemented_correctly": [],
        "implemented_partially": [],
        "not_implemented": ["LLM JSON parsing failed"],
        "hallucinated_features": [],
        "security_issues": [],
        "issues": ["Could not parse verifier LLM output as JSON"],
        "summary": "Verifier LLM output invalid",
    }


# ─────────────────────────────────────────────
#  COMPOSITE SCORER
# ─────────────────────────────────────────────

def classify_correctness(score: float) -> str:
    if score >= 85:
        return "READY"
    if score >= 75:
        return "ACCEPTABLE"
    if score >= 60:
        return "PARTIAL"
    return "REJECT"


def composite_score(l1: dict, l2: dict, l3: dict) -> dict:
    """
    Weighted composite score across all three layers.
    """
    raw = (
        l1["score"] * WEIGHTS["syntax"]     / 100 +
        l2["score"] * WEIGHTS["compliance"] / 100 +
        l3["score"] * WEIGHTS["llm"]        / 100
    )

    final = round(raw, 1)
    correctness_band = classify_correctness(final)
    return {
        "correctness_score": final,
        "correctness_band":  correctness_band,
        "threshold":         THRESHOLD,
        "overall_status":    "PASS" if final >= THRESHOLD else "FAIL",
        "layer_scores": {
            "layer1_syntax":     l1["score"],
            "layer2_compliance": l2["score"],
            "layer3_llm":        l3["score"],
        },
        "layer_weights": WEIGHTS,
    }


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    agent_path = os.getenv("GENERATED_AGENT_PY_PATH", "generated_agent/agent.py")
    main_path  = os.getenv("GENERATED_MAIN_PY_PATH", "generated_agent/main.py")
    json_path  = os.getenv("FINAL_AGENT_JSON_PATH", "final_agent.json")

    for path in [agent_path, main_path, json_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required file not found: {path}")

    agent_code = read_file(agent_path)
    main_code  = read_file(main_path)
    spec       = read_json(json_path)
    spec_text  = flatten_json(spec)

    # ── Layer 1: Syntax ────────────────────────────────────────────────────
    print("\n[Layer 1] AST Syntax Check ...")
    l1 = layer1_syntax(agent_code, main_code)
    print(f"  Score: {l1['score']}/100  |  {'PASS' if l1['passed'] else 'FAIL'}")
    if not l1["passed"]:
        for f, r in l1["details"].items():
            if r["status"] == "FAIL":
                print(f"     {f}: {r['error']} (line {r.get('line', '?')})")

    # ── Layer 2: Spec Compliance ───────────────────────────────────────────
    print("\n[Layer 2] Spec Compliance Check ...")
    l2 = layer2_compliance(agent_code, main_code, spec)
    print(f"  Score: {l2['score']}/100  |  {'PASS' if l2['passed'] else 'FAIL'}  ({l2.get('summary', '')})")
    for check, res in l2["details"].items():
        if isinstance(res, dict) and not res.get("passed"):
            print(f"     FAIL {check}: {res.get('note', '')}")

    # ── Layer 3: LLM Semantic Review ──────────────────────────────────────
    print("\n[Layer 3] Groq Semantic Review ...")
    l3 = layer3_llm(spec_text, agent_code, main_code)
    print(f"  Score: {l3['score']}/100  |  {'PASS' if l3['passed'] else 'FAIL'}")
    llm_d = l3["details"]
    if llm_d.get("not_implemented"):
        print(f"     Not implemented: {llm_d['not_implemented']}")
    if llm_d.get("hallucinated_features"):
        print(f"     Hallucinated:    {llm_d['hallucinated_features']}")
    if llm_d.get("security_issues"):
        print(f"     Security issues: {llm_d['security_issues']}")
    print(f"     Summary: {llm_d.get('summary', '')}")

    # ── Composite Score ────────────────────────────────────────────────────
    comp = composite_score(l1, l2, l3)

    print("\n" + "=" * 52)
    print(f"  CORRECTNESS SCORE : {comp['correctness_score']}/100")
    print(f"  CORRECTNESS BAND  : {comp['correctness_band']}")
    print(f"  STATUS            : {comp['overall_status']}  (threshold {THRESHOLD})")
    print("=" * 52)

    # ── Save Result ────────────────────────────────────────────────────────
    result = {
        **comp,
        "layer1_syntax":     l1,
        "layer2_compliance": l2,
        "layer3_llm":        l3,
    }

    result_path = os.getenv("VERIFIER_RESULT_PATH", "verifier_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print(f"\nSaved {result_path}")
    return result


if __name__ == "__main__":
    main()