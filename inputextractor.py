"""
inputextractor.py — Advanced Agent Specification Extractor
===========================================================
Changes from original:
 - language_selection is now wired into extract() and used in build_simple_agent_json()
 - Language from language_selection takes priority over technical_requirements
   when the user hasn't explicitly stated a language there
 - Null/empty values are filtered before applying defaults (no more empty-string overrides)
 - confirm_and_edit() supports typed values (list/bool) via JSON parsing
 - Minor: removed duplicate IMPORTANT EXTRACTION RULES block from integration_needs prompt
"""

import csv
import json
import os
import re
import sys
from typing import Any, Dict

from groq_utils import DEFAULT_GROQ_MODEL, groq_chat_json


# ===================== DEFAULTS =====================

DEFAULTS = {
    "agent_name":          "AutoAgent",
    "primary_purpose":     "General assistant",
    "capabilities":        [],
    "target_users":        "general users",
    "domain":              "general",
    "content_types":       ["text"],
    "decision_authority":  "assist only",

    "language":            "Python",
    "framework":           "None",
    "api_integrations":    [],
    "database":            "json_file",
    "cloud_platform":      "local",
    "performance":         "normal",
    "security":            "basic",
    "storage":             "json_file",
    "memory":              "in_memory",
    "third_party_tools":   [],

    "tone":                "neutral",
    "personality":         ["helpful"],
    "emotional_intelligence": "medium",

    "external_apis":           [],
    "internal_systems":        [],
    "database_connections":    [],
}


# ===================== PROMPTS =====================

EXTRACTION_PROMPTS = {

    "core_specifications": """
Extract:
- Agent Name
- Primary Purpose
- Capabilities
- Target Users
- Domain
- Content Types
- Decision Authority

You MUST return ONLY this JSON object:

{{
  "Agent Name": null,
  "Primary Purpose": null,
  "Capabilities": [],
  "Target Users": null,
  "Domain": null,
  "Content Types": [],
  "Decision Authority": null
}}

Rules:
- Use values from user input only
- If not mentioned, keep null or empty list
- Do NOT explain
- Do NOT add text outside JSON

User Input:
{input_text}
""",

    "language_selection": """
You are an expert AI systems engineer.

Based ONLY on the user's requested agent functionality, determine the most appropriate
programming language to build this agent.

Rules:
- If the user explicitly mentions a language, use exactly that
- Otherwise, choose the best language for this type of agent (prefer Python for AI/LLM agents)
- Do NOT choose a framework as a language (e.g. "LangChain" is not a language)
- Return ONE language name only
- Keep the reason concise (max 15 words)

Return ONLY JSON in this exact format:
{{
  "language": "chosen_language",
  "reason": "short technical justification",
  "user_specified": true_or_false
}}

User Input:
{input_text}
""",

    "technical_requirements": """
Extract:
- Programming language
- Framework
- APIs
- Database
- Cloud platform
- Performance
- Security
- Storage
- Memory
- Tools

You MUST return ONLY this JSON object:

{{
  "Programming language": null,
  "Framework": null,
  "APIs": [],
  "Database": null,
  "Cloud platform": null,
  "Performance": null,
  "Security": null,
  "Storage": null,
  "Memory": null,
  "Tools": []
}}

Rules:
- Use values from user input only
- If not mentioned, keep null or empty list
- Do NOT explain
- Do NOT add text outside JSON

User Input:
{input_text}
""",

    "behavioral_traits": """
Extract:
- Tone
- Personality
- Emotional intelligence

Never create new information that is not explicitly present in the user input.

You MUST return ONLY this JSON object:

{{
  "Tone": null,
  "Personality": [],
  "Emotional intelligence": null
}}

Rules:
- Use values from user input only
- If not mentioned, keep null or empty list
- Do NOT explain
- Do NOT add text outside JSON

User Input:
{input_text}
""",

    "integration_needs": """
Extract:
- External APIs
- Internal systems
- Database connections

Never create new information that is not explicitly present in the user input.

You MUST return ONLY this JSON object:

{{
  "External APIs": [],
  "Internal systems": [],
  "Database connections": []
}}

Rules:
- Use values from user input only
- If not mentioned, keep empty list
- Do NOT explain
- Do NOT add text outside JSON
- Only extract what is explicitly stated — do not infer or assume

User Input:
{input_text}
""",
}


# ===================== EXTRACTOR =====================

class AdvancedAgentExtractor:

    def __init__(self, model_name: str = DEFAULT_GROQ_MODEL):
        self.model_name = model_name

    def _extract_category(self, input_text: str, category: str) -> dict:
        prompt = EXTRACTION_PROMPTS[category].format(input_text=input_text)
        last = {}
        for _ in range(3):
            try:
                last = groq_chat_json(
                    system=(
                        "You MUST return ONLY the JSON object described in the prompt. "
                        "No markdown, no commentary, no extra keys."
                    ),
                    user=prompt,
                    model=self.model_name,
                    temperature=0.0,
                    max_tokens=900,
                ) or {}
                if isinstance(last, dict):
                    return last
            except Exception:
                continue
        return last if isinstance(last, dict) else {}

    def extract(self, user_input: str) -> Dict[str, Any]:
        state: Dict[str, Any] = {"input_text": user_input}

        print("  Extracting core specifications ...")
        state["core_specifications"]   = self._extract_category(user_input, "core_specifications")

        # Language selection is now a dedicated, reliable call
        print("  Selecting programming language ...")
        state["language_selection"]    = self._extract_category(user_input, "language_selection")

        print("  Extracting technical requirements ...")
        state["technical_requirements"] = self._extract_category(user_input, "technical_requirements")

        print("  Extracting behavioral traits ...")
        state["behavioral_traits"]     = self._extract_category(user_input, "behavioral_traits")

        print("  Extracting integration needs ...")
        state["integration_needs"]     = self._extract_category(user_input, "integration_needs")

        return state


# ===================== VALUE HELPERS =====================

def _is_empty(value: Any) -> bool:
    """Returns True if a value should be treated as 'not provided'."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "none", "n/a", "null"):
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _clean_list(values: Any) -> list:
    if not isinstance(values, list):
        return []
    out = []
    seen = set()
    for item in values:
        s = str(item).strip()
        if not s or s.lower() in ("none", "null", "n/a"):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _resolve_language(tech: dict, lang_sel: dict) -> str:
    """
    Language resolution priority:
      1. Explicit language in technical_requirements (user typed it there)
      2. language_selection result (intelligent LLM pick)
      3. Default: Python
    """
    tech_lang = tech.get("Programming language")
    if not _is_empty(tech_lang):
        return tech_lang  # User explicitly stated it in tech requirements

    sel_lang = lang_sel.get("language")
    if not _is_empty(sel_lang):
        return sel_lang   # LLM-selected best language

    return DEFAULTS["language"]


# ===================== CLEAN JSON BUILDER =====================

def build_simple_agent_json(state: Dict[str, Any]) -> dict:

    core    = state.get("core_specifications",   {})
    tech    = state.get("technical_requirements", {})
    beh     = state.get("behavioral_traits",     {})
    integ   = state.get("integration_needs",     {})
    lang_sel = state.get("language_selection",   {})

    # Resolved language (priority: tech_req > language_selection > default)
    resolved_language = _resolve_language(tech, lang_sel)

    # Attach language selection reasoning for transparency
    language_note = lang_sel.get("reason", "")
    user_specified = lang_sel.get("user_specified", False)

    agent = {
        "user_input":         state.get("input_text", ""),

        # Core
        "agent_name":         core.get("Agent Name"),
        "primary_purpose":    core.get("Primary Purpose"),
        "capabilities":       core.get("Capabilities"),
        "target_users":       core.get("Target Users"),
        "domain":             core.get("Domain"),
        "content_types":      core.get("Content Types"),
        "decision_authority": core.get("Decision Authority"),

        # Technical
        "language":           resolved_language,
        "language_reason":    language_note,
        "language_user_specified": user_specified,
        "framework":          tech.get("Framework"),
        "api_integrations":   tech.get("APIs"),
        "database":           tech.get("Database"),
        "cloud_platform":     tech.get("Cloud platform"),
        "performance":        tech.get("Performance"),
        "security":           tech.get("Security"),
        "storage":            tech.get("Storage"),
        "memory":             tech.get("Memory"),
        "third_party_tools":  tech.get("Tools"),

        # Behavioral
        "tone":               beh.get("Tone"),
        "personality":        beh.get("Personality"),
        "emotional_intelligence": beh.get("Emotional intelligence"),

        # Integration
        "external_apis":         integ.get("External APIs"),
        "internal_systems":      integ.get("Internal systems"),
        "database_connections":  integ.get("Database connections"),
    }

    # Apply defaults only for fields that are truly empty
    # (prevents overwriting valid values like "None" framework with the default)
    for key, default_val in DEFAULTS.items():
        if _is_empty(agent.get(key)):
            agent[key] = default_val

    # Normalize list/string quality for downstream generator.
    list_fields = [
        "capabilities", "content_types", "api_integrations", "third_party_tools",
        "personality", "external_apis", "internal_systems", "database_connections",
    ]
    for field in list_fields:
        agent[field] = _clean_list(agent.get(field))

    for field in ["agent_name", "primary_purpose", "target_users", "domain", "language", "framework"]:
        if field in agent and isinstance(agent[field], str):
            agent[field] = " ".join(agent[field].strip().split())

    if not agent["capabilities"]:
        # Never output empty capabilities; this hurts code generation quality.
        purpose = agent.get("primary_purpose", "").strip()
        agent["capabilities"] = [purpose if purpose else "Perform the primary task reliably"]

    # Remove internal helper keys from final JSON if not needed
    # (comment out these lines if you want to keep them for transparency)
    # agent.pop("language_reason", None)
    # agent.pop("language_user_specified", None)

    return agent


# ===================== CONFIRM LOOP =====================

def confirm_and_edit(agent_json: dict) -> dict:
    """
    Interactive confirmation loop.
    Supports typed values: entering a JSON-parseable value updates the field correctly.
    Example:  capabilities=["scrape", "summarize", "email"]
    """
    while True:
        print("\n── Generated Agent JSON ──────────────────────────")
        print(json.dumps(agent_json, indent=2))
        print("──────────────────────────────────────────────────")

        choice = input("\nProceed? (yes / edit / show-language): ").strip().lower() or "yes"

        if choice == "yes":
            return agent_json

        if choice == "show-language":
            print(f"\n  Language : {agent_json.get('language')}")
            print(f"  Reason   : {agent_json.get('language_reason', 'N/A')}")
            print(f"  User specified: {agent_json.get('language_user_specified', False)}")
            continue

        if choice == "edit":
            change = input("Enter field=value  (e.g.  language=JavaScript) : ").strip()
            if "=" in change:
                key, raw_val = change.split("=", 1)
                key = key.strip()
                raw_val = raw_val.strip()

                # Try to parse as JSON (handles lists, booleans, numbers)
                try:
                    value = json.loads(raw_val)
                except json.JSONDecodeError:
                    value = raw_val  # Keep as plain string

                if key in agent_json:
                    agent_json[key] = value
                    # Keep normalized even after edits.
                    if key in ("capabilities", "content_types", "api_integrations", "third_party_tools",
                               "personality", "external_apis", "internal_systems", "database_connections"):
                        agent_json[key] = _clean_list(agent_json[key])
                    print(f"  ✓ Updated '{key}' → {value}")
                else:
                    print(f"  ⚠ Field '{key}' not found. Available fields:")
                    print("   ", list(agent_json.keys()))
            else:
                print("  ⚠ Invalid format. Use:  field=value")


# ===================== MAIN =====================

if __name__ == "__main__":
    csv_path = os.getenv("INPUT_CSV_PATH", "input.csv")
    if not os.path.exists(csv_path):
        print(f"⚠  {csv_path} not found.")
        sys.exit(1)

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("⚠  input.csv is empty.")
        sys.exit(1)

    user_input = rows[-1]["user_input"]   # always uses the latest entry
    preview    = user_input[:80] + ("..." if len(user_input) > 80 else "")
    print(f'\nRead input from {csv_path}: "{preview}"')

    extractor = AdvancedAgentExtractor()
    state     = extractor.extract(user_input)

    agent_json  = build_simple_agent_json(state)
    final_agent = confirm_and_edit(agent_json)

    output_path = os.getenv("FINAL_AGENT_JSON_PATH", "final_agent.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_agent, f, indent=2)

    print(f"\n✓ Saved as {output_path}")
    print("  Agent ready!")