"""
========================================================
 PERSPECTIVE EXTRACTOR AGENT
 Configuration-Driven Agentic System
========================================================
 Model  : mistral:7b (via Ollama)
 Role   : Classify user input as 'agent_building' or
          'conversational', then route accordingly.
 Routes :
   agent_building  → JSON Extractor Agent (plain text)
   conversational  → Code Interface Agent (with response)
========================================================
"""

import os
import sys

import requests
import json
import re
import logging
import csv
from typing import Dict, Any

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
OLLAMA_BASE_URL  = "http://localhost:11434"
MODEL            = "llama3.2"
REQUEST_TIMEOUT  = 120          # seconds
MAX_INPUT_LENGTH = 5000        # characters
MIN_INPUT_LENGTH = 3           # characters

# ─────────────────────────────────────────────
#  LOGGER
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("PerspectiveAgent")


# ─────────────────────────────────────────────
#  PROMPTS
# ─────────────────────────────────────────────

CLASSIFICATION_PROMPT = """\
You are a Perspective Extractor Agent in a Configuration-Driven Agentic System.

Your ONLY job is to analyze the user input and output a single JSON object — nothing else.

──────────────────────────────────────────────
CLASSIFICATION RULES
──────────────────────────────────────────────
Classify as "agent_building" if the user wants to:
  • BUILD, CREATE, MAKE, GENERATE, DEVELOP, DESIGN, WRITE, or SET UP
    any kind of agent / tool / script / pipeline / bot / automation / workflow.

  Examples:
    "Build me an agent that reads a CSV and extracts named entities"
    "Create a Python script that monitors a folder and sends email alerts"
    "Make an automation that scrapes a website daily"
    "Write a tool that summarises PDFs"

Classify as "conversational" if the user is:
  • Asking a general question, seeking information, or having a discussion.
  • NOT requesting any kind of build or creation.

  Examples:
    "What is an LLM agent?"
    "How does RAG work?"
    "Explain prompt engineering"
    "What are the best open-source LLMs?"

IMPORTANT:
  • If the input is ambiguous but contains ANY hint of building/creating/automating → "agent_building"
  • Never classify greetings, single words, or off-topic input as "agent_building"
  • user_text must be the cleaned, plain-text version of the user's request (no JSON, no markdown)

──────────────────────────────────────────────
RESPOND IN THIS EXACT JSON FORMAT — NO OTHER TEXT:
──────────────────────────────────────────────
{{
  "classification": "agent_building" or "conversational",
  "user_text": "<cleaned plain text of the user request>",
  "confidence": "high" or "medium" or "low",
  "reason": "<one sentence explaining your classification>"
}}

User Input: {user_input}
"""

CONVERSATIONAL_PROMPT = """\
You are a knowledgeable and friendly AI assistant specialising in AI agents, \
LLMs, automation systems, and software engineering.

Answer the following question clearly, accurately, and concisely.
Do NOT hallucinate. If you are unsure, say so honestly.

After your answer, ALWAYS end with exactly this section (do not skip it):

---
💡 Agent Opportunity: [Suggest ONE specific, practical agent the user could build \
that directly relates to their question — keep it to 1–2 sentences.]

Question: {user_input}
"""


# ─────────────────────────────────────────────
#  OLLAMA CALLER
# ─────────────────────────────────────────────

def call_ollama(prompt: str, temperature: float = 0.1) -> str:
    """
    Send a prompt to the local Ollama instance and return the response text.

    Args:
        prompt      : The full prompt string.
        temperature : Sampling temperature (lower = more deterministic).

    Returns:
        Raw string response from the model.

    Raises:
        ConnectionError : Ollama is not reachable.
        TimeoutError    : Request exceeded REQUEST_TIMEOUT seconds.
        RuntimeError    : Any other HTTP or parsing error.
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 512,
        }
    }

    try:
        logger.debug("Calling Ollama (%s) ...", MODEL)
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        logger.debug("Ollama responded (%d chars)", len(text))
        return text

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"❌ Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
            "Please make sure Ollama is running (`ollama serve`)."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"❌ Ollama request timed out after {REQUEST_TIMEOUT}s. "
            "Try again or increase REQUEST_TIMEOUT."
        )
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"❌ Ollama HTTP error: {exc}")
    except (KeyError, ValueError) as exc:
        raise RuntimeError(f"❌ Failed to parse Ollama response: {exc}")


# ─────────────────────────────────────────────
#  JSON EXTRACTOR (ROBUST)
# ─────────────────────────────────────────────

def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    Robustly extract and parse the classification JSON from the model's response.
    Falls back gracefully if the model produces extra text around the JSON.

    Priority:
      1. Direct JSON parse
      2. Regex extraction of JSON block containing 'classification'
      3. Keyword-based fallback
      4. Default to 'conversational'
    """

    # 1. Direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 2. Extract JSON block with 'classification' key
    pattern = r'\{[^{}]*"classification"[^{}]*\}'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 3. Find any JSON-like block
    for block in re.findall(r'\{.*?\}', response, re.DOTALL):
        try:
            parsed = json.loads(block)
            if "classification" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue

    # 4. Keyword fallback
    lower = response.lower()
    logger.warning("Could not parse JSON from model response — using keyword fallback.")
    if "agent_building" in lower or "agent building" in lower:
        return {
            "classification": "agent_building",
            "user_text": response,
            "confidence": "low",
            "reason": "Keyword fallback: 'agent_building' found in response."
        }

    # 5. Safe default
    return {
        "classification": "conversational",
        "user_text": response,
        "confidence": "low",
        "reason": "Default fallback: could not determine classification."
    }


# ─────────────────────────────────────────────
#  INPUT VALIDATOR
# ─────────────────────────────────────────────

def validate_input(user_input: str) -> str:
    """
    Validate and sanitise raw user input.

    Raises:
        ValueError : If input is empty, too short, or too long.
    """
    if not isinstance(user_input, str):
        raise ValueError("Input must be a string.")

    user_input = user_input.strip()

    if not user_input:
        raise ValueError("User input cannot be empty. Please type something.")

    if len(user_input) < MIN_INPUT_LENGTH:
        raise ValueError(
            f"Input too short ({len(user_input)} chars). "
            "Please describe what you need in more detail."
        )

    if len(user_input) > MAX_INPUT_LENGTH:
        raise ValueError(
            f"Input too long ({len(user_input)} chars). "
            f"Please keep it under {MAX_INPUT_LENGTH} characters."
        )

    # Strip potential injection attempts (basic sanitisation)
    # Remove sequences that could manipulate the system prompt
    user_input = re.sub(r'(system\s*prompt|ignore\s+previous|you\s+are\s+now)', '', user_input, flags=re.IGNORECASE)

    return user_input


# ─────────────────────────────────────────────
#  MAIN AGENT
# ─────────────────────────────────────────────

def perspective_agent(user_input: str) -> Dict[str, Any]:
    """
    Perspective Extractor Agent — main entry point.

    Steps:
      1. Validate input
      2. Call Mistral to classify: 'agent_building' or 'conversational'
      3. Route accordingly:
         - agent_building  → returns plain text for JSON Extractor Agent
         - conversational  → answers question + nudges toward agent building

    Args:
        user_input (str): Raw natural language text from the user.

    Returns:
        Dict with the following keys:
          route                 : 'json_extractor' | 'code_interface'
          classification        : 'agent_building' | 'conversational'
          user_text             : plain text for downstream agent
          conversational_response : str | None  (only for conversational)
          confidence            : 'high' | 'medium' | 'low'
          reason                : why this classification was chosen
          original_input        : the original user input (unchanged)
    """

    logger.info("─" * 50)
    logger.info("Perspective Agent received input (%d chars)", len(user_input))

    # ── Step 1: Validate ──────────────────────
    user_input = validate_input(user_input)

    # ── Step 2: Classify ──────────────────────
    logger.info("Classifying input ...")
    classification_prompt = CLASSIFICATION_PROMPT.format(user_input=user_input)
    raw_response = call_ollama(classification_prompt, temperature=0.1)
    logger.debug("Raw classification response:\n%s", raw_response)

    # ── Step 3: Parse classification ──────────
    parsed = extract_json_from_response(raw_response)

    classification = parsed.get("classification", "conversational").lower().strip()
    user_text      = parsed.get("user_text", user_input).strip()
    confidence     = parsed.get("confidence", "medium").lower().strip()
    reason         = parsed.get("reason", "No reason provided.")

    # Validate classification value — only allow known values
    if classification not in ("agent_building", "conversational"):
        logger.warning("Unknown classification '%s' — defaulting to 'conversational'", classification)
        classification = "conversational"

    # Validate confidence value
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    logger.info("Classification: %s (confidence: %s)", classification.upper(), confidence)
    logger.info("Reason: %s", reason)

    # ── Step 4: Route ─────────────────────────

    # ── PATH A: Agent Building ─────────────────
    if classification == "agent_building":
        logger.info("Route → JSON Extractor Agent")
        return {
            "route"                  : "json_extractor",
            "classification"         : "agent_building",
            "user_text"              : user_text,
            "conversational_response": None,
            "confidence"             : confidence,
            "reason"                 : reason,
            "original_input"         : user_input
        }

    # ── PATH B: Conversational ─────────────────
    else:
        logger.info("Route → Code Interface Agent (conversational)")
        conv_prompt = CONVERSATIONAL_PROMPT.format(user_input=user_input)
        conversational_response = call_ollama(conv_prompt, temperature=0.7)

        return {
            "route"                  : "code_interface",
            "classification"         : "conversational",
            "user_text"              : user_text,
            "conversational_response": conversational_response,
            "confidence"             : confidence,
            "reason"                 : reason,
            "original_input"         : user_input
        }


# ─────────────────────────────────────────────
#  MAIN  (python perspective_agent.py)
# ─────────────────────────────────────────────

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

    try:
        result = perspective_agent(user_input)

        # Route-based output filename
        if result["route"] == "json_extractor":
            output_file = "build_agent_output.json"
        else:
            output_file = "conversational_output.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"\n✅ Output saved to {output_file}")
        print(json.dumps(result, indent=2))

    except (ValueError, ConnectionError, TimeoutError, RuntimeError) as exc:
        print(f"\n⚠  Error: {exc}")