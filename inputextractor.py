# advanced_extractor_agent.py
import csv
import json
import os
import re
import asyncio
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from langgraph.graph import StateGraph, END

# Ollama import fix
try:
    from langchain_ollama import OllamaLLM as Ollama
    print("Using updated Ollama import")
except ImportError:
    from langchain_community.llms import Ollama
    print("Using legacy Ollama import")


# ===================== DEFAULTS =====================

DEFAULTS = {
    "agent_name": "AutoAgent",
    "primary_purpose": "General assistant",
    "capabilities": [],
    "target_users": "general users",
    "domain": "general",
    "content_types": ["text"],
    "decision_authority": "assist only",

    "language": "Python",
    "framework": "None",
    "api_integrations": [],
    "database": "json_file",
    "cloud_platform": "local",
    "performance": "normal",
    "security": "basic",
    "storage": "json_file",
    "memory": "in_memory",
    "third_party_tools": [],

    "tone": "neutral",
    "personality": ["helpful"],
    "emotional_intelligence": "medium",

    "external_apis": [],
    "internal_systems": [],
    "database_connections": [],
}


# ===================== CATEGORIES =====================

class ExtractionCategory(str, Enum):
    CORE_SPEC = "core_specifications"
    TECH_REQ = "technical_requirements"
    BEHAVIORAL = "behavioral_traits"
    INTEGRATION = "integration_needs"


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

Based ONLY on the user’s requested agent functionality, determine the most appropriate programming language to build this agent.check if user has already mentioned a programming language or you figure out the best one.


Rules:
- Choose a language commonly used for this type of AI agent
- Prefer ecosystem strength (LLMs, APIs, tooling)
- Do NOT choose frameworks as languages
- Return ONE language only
- If the user explicitly mentions a language, use that
- Otherwise intelligently select the best option

Return ONLY JSON in this format:

{
  "language": "chosen_language",
  "reason": "short technical justification"
}

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
  "Emotional intelligence": null,
}}

Rules:
- Use values from user input only
- If not mentioned, keep null or empty list
- Do NOT explain
- Do NOT add text outside JSON

Never create new information that is not explicitly present in the user input.


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
  "Database connections": [],
}}

Rules:
- Use values from user input only
- If not mentioned, keep empty list
- Do NOT explain
- Do NOT add text outside JSON

Never create new information that is not explicitly present in the user input.


User Input:
{input_text}

IMPORTANT EXTRACTION RULES:

• Only extract information that is explicitly stated in the user input
• Do NOT infer, guess, assume, or generalize
• If a value is not clearly mentioned, return null or an empty list
• Do NOT map tools into behavior fields
• Do NOT convert frameworks into programming languages
• Do NOT fill every field just to complete JSON
• Accuracy is more important than completeness

Output must strictly follow the JSON template.
"""
}

# ===================== EXTRACTOR =====================

class AdvancedAgentExtractor:

    def __init__(self, model_name="mistral:7b"):
        self.model = Ollama(model=model_name)
        self.graph = self._create_graph()

    def _create_graph(self):
        workflow = StateGraph(dict)

        for cat in ExtractionCategory:
            workflow.add_node(cat.value, self._make_node(cat.value))

        workflow.add_edge("__start__", ExtractionCategory.CORE_SPEC.value)

        cats = [c.value for c in ExtractionCategory]
        for i in range(len(cats) - 1):
            workflow.add_edge(cats[i], cats[i + 1])

        workflow.add_edge(cats[-1], END)
        return workflow.compile()

    def _make_node(self, category):
        async def node(state):
            return await self._extract_node(state, category)
        return node

    async def _extract_node(self, state, category):
        if "input_text" not in state:
            return state

        prompt = EXTRACTION_PROMPTS[category].format(
            input_text=state["input_text"]
        )

        response = await self.model.ainvoke(prompt)

        parsed = self._parse_json(response)

        state[category] = parsed or {}
        return state

    def _parse_json(self, text):
        try:
            return json.loads(text.strip())
        except:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return None

    def extract(self, user_input):
        return asyncio.run(
            self.graph.ainvoke({"input_text": user_input})
        )


# ===================== CLEAN JSON BUILDER =====================

def build_simple_agent_json(state):

    core = state.get("core_specifications", {})
    tech = state.get("technical_requirements", {})
    beh = state.get("behavioral_traits", {})
    integ = state.get("integration_needs", {})

    agent = {
        "user input": state.get("input_text", ""),
        "agent_name": core.get("Agent Name"),
        "primary_purpose": core.get("Primary Purpose"),
        "capabilities": core.get("Capabilities"),
        "target_users": core.get("Target Users"),
        "domain": core.get("Domain"),
        "content_types": core.get("Content Types"),
        "decision_authority": core.get("Decision Authority"),

        "language": tech.get("Programming language"),
        "framework": tech.get("Framework"),
        "api_integrations": tech.get("APIs"),
        "database": tech.get("Database"),
        "cloud_platform": tech.get("Cloud platform"),
        "performance": tech.get("Performance"),
        "security": tech.get("Security"),
        "storage": tech.get("Storage"),
        "memory": tech.get("Memory"),
        "third_party_tools": tech.get("Tools"),

        "tone": beh.get("Tone"),
        "personality": beh.get("Personality"),
        "emotional_intelligence": beh.get("Emotional intelligence"),
        "response_length": beh.get("Response length"),

        "external_apis": integ.get("External APIs"),
        "internal_systems": integ.get("Internal systems"),
        "database_connections": integ.get("Database connections"),
        "messaging_systems": integ.get("Messaging systems")
    }

    for k, v in DEFAULTS.items():
        if not agent.get(k):
            agent[k] = v

    return agent


# ===================== CONFIRM LOOP =====================

def confirm_and_edit(agent_json):

    while True:
        print("\nGenerated Agent JSON:\n")
        print(json.dumps(agent_json, indent=2))

        choice = input("\nProceed? (yes/edit): ").lower()

        if choice == "yes":
            return agent_json

        if choice == "edit":
            change = input("field=value : ")
            if "=" in change:
                k, v = change.split("=", 1)
                agent_json[k.strip()] = v.strip()


# ===================== MAIN =====================

if __name__ == "__main__":

    csv_path = "input.csv"
    if not os.path.exists(csv_path):
        print(f"⚠  {csv_path} not found.")
        sys.exit(1)

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("⚠  input.csv is empty.")
        sys.exit(1)

    user_input = rows[-1]["user_input"]   # always uses the latest entry
    print(f"Read input from {csv_path}: \"{user_input[:80]}{'...' if len(user_input) > 80 else ''}\"")

    extractor = AdvancedAgentExtractor()
    state = extractor.extract(user_input)

    agent_json = build_simple_agent_json(state)

    final_agent = confirm_and_edit(agent_json)

    with open("final_agent.json", "w") as f:
        json.dump(final_agent, f, indent=2)

    print("\nSaved as final_agent.json")
    print("Agent ready!")
