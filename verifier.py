import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

THRESHOLD    = 60
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL        = "llama-3.3-70b-versatile"


# ─────────────────────────────────────────────
#  FILE HELPERS
# ─────────────────────────────────────────────

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_json(data):
    """Converts JSON spec into readable text for the prompt."""
    return json.dumps(data, indent=2)


# ─────────────────────────────────────────────
#  GROQ AI CORRECTNESS CHECK
# ─────────────────────────────────────────────

SYSTEM_VERIFIER = """\
You are a senior Python code reviewer. Your job is to evaluate whether generated Python code
correctly implements a given agent specification.

You must respond with a single valid JSON object — no markdown, no prose, no fences.

The JSON must have exactly these keys:
{
  "correctness_percentage": <integer 0-100>,
  "implemented_correctly":  [list of spec items that are correctly implemented],
  "implemented_partially":  [list of spec items that are partially implemented],
  "not_implemented":        [list of spec items missing entirely],
  "issues":                 [list of specific problems found in the code],
  "summary":                "one sentence overall verdict"
}
"""


def groq_correctness_check(spec_json: str, agent_code: str, main_code: str) -> dict:
    """
    Sends spec + code to Groq and returns a structured correctness review.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY not set. "
            "Set it with: set GROQ_API_KEY=your_key_here  (Windows CMD)\n"
            "or add it to your .env file."
        )

    client = Groq(api_key=GROQ_API_KEY)

    user_prompt = f"""\
=== AGENT SPECIFICATION (JSON) ===
{spec_json}

=== agent.py ===
{agent_code}

=== main.py ===
{main_code}

Review the code against the specification and respond with the JSON object described in your instructions.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_VERIFIER},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    agent_path = "generated_agent/agent.py"
    main_path  = "generated_agent/main.py"
    json_path  = "final_agent.json"

    if not os.path.exists(agent_path):
        raise FileNotFoundError("agent.py not found")
    if not os.path.exists(main_path):
        raise FileNotFoundError("main.py not found")
    if not os.path.exists(json_path):
        raise FileNotFoundError("final_agent.json not found")

    agent_code = read_file(agent_path)
    main_code  = read_file(main_path)
    json_data  = read_json(json_path)
    json_text  = flatten_json(json_data)

    print("Running Groq AI correctness review ...")
    ai_review = groq_correctness_check(json_text, agent_code, main_code)

    ai_pct = ai_review.get("correctness_percentage")
    result = {
        "ai_review":                      ai_review,
        "overall_correctness_percentage": ai_pct,
        "threshold":                      THRESHOLD,
        "overall_status":                 "PASS" if isinstance(ai_pct, int) and ai_pct >= THRESHOLD else "FAIL",
    }

    with open("verifier_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Verification complete")
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()