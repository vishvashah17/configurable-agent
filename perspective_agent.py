"""
========================================================
 PERSPECTIVE EXTRACTOR AGENT  (v2 — improved classifier)
 Configuration-Driven Agentic System
========================================================
 Fixes over v1:
   1. Fatal "ANY hint" bias rule removed
   2. Clear "TO build" vs "HOW to build" distinction added
   3. 16 few-shot examples added to prompt (8 per class + edge cases)
   4. Rule-based pre-classifier added (zero LLM cost for obvious cases)
   5. Third route: needs_clarification for genuinely ambiguous inputs
   6. Confidence gate: low confidence → ask user to clarify
   7. extract_json_from_response wired into the actual flow
   8. validate_input no longer silently modifies the prompt
========================================================
"""

import csv
import json
import logging
import os
import re
import sys
from typing import Any, Dict, Optional

from groq_utils import DEFAULT_GROQ_MODEL, groq_chat, groq_chat_json

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
MODEL            = DEFAULT_GROQ_MODEL
MAX_INPUT_LENGTH = 5000
MIN_INPUT_LENGTH = 10   # raised from 3 — anything shorter is meaningless

# ─────────────────────────────────────────────
#  LOGGER
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("PerspectiveAgent")


# ─────────────────────────────────────────────
#  LAYER 0 — RULE-BASED PRE-CLASSIFIER
#  (zero LLM cost, runs before any API call)
# ─────────────────────────────────────────────

# Unambiguously conversational — these patterns mean the user is ASKING, not REQUESTING
CONVERSATIONAL_RULES = [
    # Question openers
    r"^(what|how|why|when|where|who|which|can you explain|explain|tell me|describe|help me understand)",
    r"^(what is|what are|what does|what's the difference|what would)",
    r"^(how does|how do|how would|how can i|how should)",
    r"^(why does|why is|why would|why should)",
    r"^(is it possible|is there a way|could you explain|do you know)",
    r"^(give me an overview|summarize|compare|contrast|pros and cons|advantages)",
    r"^(i want to (know|understand|learn|find out))",
    # Greetings / chitchat
    r"^(hello|hi|hey|good morning|good evening|sup|what's up|how are you)",
    # Single/short knowledge questions
    r"^(what is (an?|the) \w+\??$)",
    r"difference between",
    r"best practices? for",
    r"recommend.{0,30}(tool|library|framework|language|approach)",
]

# Unambiguously agent_building — direct imperative + object
AGENT_BUILDING_RULES = [
    # Direct imperatives: "build me", "create a", "make me", "generate a", "write me a"
    r"^(build|create|make|generate|write|develop|design|set up|implement|code|program|construct)\s+(me\s+)?(a|an|the|my)\s+",
    # "I want you to build / I need you to create"
    r"^i (want|need) (you |us )?(to )?(build|create|make|generate|write|develop|design|code|implement)\s+(a|an|the|my)?\s*",
    # "Can you build / Could you create"
    r"^(can|could|would|please) you (build|create|make|generate|write|develop|design|code|implement)\s+",
    # "Help me build" (NOT "help me understand how to build")
    r"^help me (build|create|make|generate|write|code|develop|design|implement)\s+(a|an|the|my)?\s+\w+\s+(?!that (works|explains|shows|teaches))",
    # "I need a [thing] that does X"
    r"^i need (a|an|the|my) \w+ (agent|bot|script|tool|automation|pipeline|workflow|system|assistant)\s+that\s+",
]

# Patterns that suggest prompt injection regardless of classification
INJECTION_PATTERNS = [
    r"ignore (all |previous |above |prior )?instructions",
    r"disregard (your |all )?instructions",
    r"forget (everything|all|your instructions)",
    r"you are now\s+\w",
    r"new (system )?persona",
    r"your (real |true )?instructions are",
    r"act as (an? )?(unrestricted|evil|jailbreak|dan\b)",
    r"developer mode",
    r"pretend (you have no|you are)",
    r"repeat (everything|your (system|instructions))",
    r"print your (system prompt|instructions)",
    r"output your (full |entire )?prompt",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__import__",
]


def pre_classify(text: str) -> Optional[str]:
    """
    Rule-based classification — returns 'agent_building', 'conversational',
    or None (meaning: unknown, fall through to LLM).

    Runs before any LLM call. Order matters:
      1. Injection check  → block
      2. agent_building   → clear imperatives
      3. conversational   → clear knowledge queries
      4. None             → send to LLM
    """
    lower = text.lower().strip()

    # 1. Injection check — block early
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning("Pre-classifier: injection pattern detected — blocking")
            return "injection_blocked"

    # 2. Clear agent_building
    for pattern in AGENT_BUILDING_RULES:
        if re.search(pattern, lower):
            logger.info("Pre-classifier: agent_building (rule match)")
            return "agent_building"

    # 3. Clear conversational
    for pattern in CONVERSATIONAL_RULES:
        if re.search(pattern, lower):
            logger.info("Pre-classifier: conversational (rule match)")
            return "conversational"

    # 4. Ambiguous — needs LLM
    return None


# ─────────────────────────────────────────────
#  CLASSIFICATION PROMPT  (v2)
#  Key fixes vs v1:
#   - "TO build" vs "ABOUT building" rule
#   - Removed "ANY hint" bias
#   - 16 few-shot examples (8 agent_building + 8 conversational)
#   - Third class: needs_clarification
# ─────────────────────────────────────────────

CLASSIFICATION_PROMPT = """\
You are a Perspective Extractor Agent. Your ONLY job is to classify the user's intent.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE ONE CRITICAL RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The difference between "agent_building" and "conversational" is:

  agent_building  = user is REQUESTING you to BUILD something right now.
                    It is a DIRECT ACTION REQUEST. A command. An imperative.

  conversational  = user is ASKING a QUESTION, seeking KNOWLEDGE, or having a DISCUSSION.
                    Even if the topic is about building agents, it is still conversational
                    if they are asking HOW or WHY rather than saying DO IT.

  needs_clarification = the input is so vague, incomplete, or ambiguous that you
                        cannot reliably determine what the user wants.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLES — STUDY THESE CAREFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_BUILDING examples (direct build requests):
  ✓ "Build me an agent that reads emails and summarizes them"
  ✓ "Create a Python script that monitors a folder and sends Slack alerts"
  ✓ "Make me a web scraping bot that extracts product prices from Amazon"
  ✓ "I need an agent that translates CSV files to JSON"
  ✓ "Can you generate a tool that tracks stock prices and emails alerts?"
  ✓ "Write me a chatbot that answers questions from a PDF document"
  ✓ "I want you to develop an automation that posts tweets daily"
  ✓ "Help me build a sentiment analysis pipeline for customer reviews"

CONVERSATIONAL examples (questions, knowledge, discussion — NOT build requests):
  ✓ "What is an LLM agent?"                                    ← knowledge question
  ✓ "How do I build a web scraper in Python?"                  ← asking HOW, not requesting TO
  ✓ "What's the difference between RAG and fine-tuning?"       ← comparison question
  ✓ "How does a multi-agent pipeline work?"                    ← asking HOW it works
  ✓ "What are the best frameworks for building AI agents?"     ← recommendation question
  ✓ "Can you explain prompt engineering?"                      ← explanation request
  ✓ "I want to understand how LangChain works"                 ← learning intent
  ✓ "What should I know before building an AI agent?"          ← knowledge-seeking

NEEDS_CLARIFICATION examples (too vague to determine):
  ✓ "agent"                         ← single word, no intent
  ✓ "help me"                       ← no context
  ✓ "I need something for my work"  ← completely vague
  ✓ "make it better"                ← no object, no context

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASSIFICATION DECISION TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1: Does the user use an IMPERATIVE verb directed at YOU?
        (build, create, make, generate, write, develop, design, code, help me build...)
        → If YES and they want an OUTPUT → agent_building
        → If YES but they're asking about concepts → conversational

Step 2: Is the user ASKING a question or seeking information?
        (what, how, why, explain, tell me, compare, recommend, understand...)
        → conversational (even if the topic is about building agents)

Step 3: Is it too vague to tell?
        → needs_clarification

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPOND WITH ONLY THIS JSON — NO OTHER TEXT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "classification": "agent_building" or "conversational" or "needs_clarification",
  "user_text": "<cleaned plain-text version of the user request — no JSON, no markdown>",
  "confidence": "high" or "medium" or "low",
  "reason": "<one sentence: cite the specific words that determined your classification>"
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

---
✅ Next step: If you want me to build an agent, reply with a prompt like:
"Build me an agent that ..."

Question: {user_input}
"""

CLARIFICATION_PROMPT = """\
The user's request is unclear and needs more detail before we can build anything useful.
Reply in a friendly, helpful tone. Ask ONE focused clarifying question that, once answered,
would let us determine exactly what to build.

Keep your reply to 2–3 sentences maximum. No lists. No headers.

Unclear input: "{user_input}"
"""


# ─────────────────────────────────────────────
#  JSON EXTRACTOR (ROBUST)
#  Now actually wired into the flow
# ─────────────────────────────────────────────

def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    4-tier JSON extraction:
      1. Direct parse
      2. Strip markdown fences, re-parse
      3. Regex extract first {...} block containing 'classification'
      4. Keyword fallback → default to 'needs_clarification'
    """
    # 1. Direct parse
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Strip markdown fences
    cleaned = response.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        for part in parts:
            candidate = part.strip().lstrip("json").strip()
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue

    # 3. Regex extract JSON block containing 'classification'
    for block in re.findall(r'\{[^{}]*"classification"[^{}]*\}', response, re.DOTALL):
        try:
            return json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue

    # Broader fallback: any {...} block
    for block in re.findall(r'\{.*?\}', response, re.DOTALL):
        try:
            parsed = json.loads(block)
            if "classification" in parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue

    # 4. Keyword fallback
    logger.warning("Could not parse JSON from model response — using keyword fallback")
    lower = response.lower()
    if "agent_building" in lower:
        return {"classification": "agent_building",  "user_text": response, "confidence": "low", "reason": "Keyword fallback"}
    if "conversational" in lower:
        return {"classification": "conversational",  "user_text": response, "confidence": "low", "reason": "Keyword fallback"}

    # Safe default — prefer asking for clarification over guessing wrong
    return {"classification": "needs_clarification", "user_text": response, "confidence": "low", "reason": "Could not parse model response"}


# ─────────────────────────────────────────────
#  INPUT VALIDATOR  (v2)
#  No longer silently modifies the input text.
#  Only raises errors for genuinely invalid input.
# ─────────────────────────────────────────────

def validate_input(user_input: str) -> str:
    """
    Validates and lightly normalizes raw user input.

    Changes from v1:
    - Does NOT silently strip/modify content with regex (that changed meaning
      and could corrupt legitimate requests)
    - Raises ValueError with user-friendly messages
    - Returns normalized (strip + NFKC unicode) version only
    """
    import unicodedata

    if not isinstance(user_input, str):
        raise ValueError("Input must be a string.")

    # Normalize unicode (handles smart quotes, full-width chars, etc.)
    user_input = unicodedata.normalize("NFKC", user_input).strip()

    if not user_input:
        raise ValueError("Input cannot be empty. Please describe what you need.")

    if len(user_input) < MIN_INPUT_LENGTH:
        raise ValueError(
            f"Input is too short ({len(user_input)} chars). "
            "Please give more detail about what you'd like to build or ask."
        )

    if len(user_input) > MAX_INPUT_LENGTH:
        raise ValueError(
            f"Input is too long ({len(user_input)} chars). "
            f"Please keep it under {MAX_INPUT_LENGTH} characters."
        )

    # Block null bytes and control characters (not injection — actual invalid data)
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', user_input):
        raise ValueError("Input contains invalid control characters.")

    return user_input


# ─────────────────────────────────────────────
#  LLM CLASSIFIER  (with extract_json_from_response)
# ─────────────────────────────────────────────

def llm_classify(user_input: str) -> Dict[str, Any]:
    """
    Sends input to Groq for classification.
    Uses extract_json_from_response for robust JSON handling.
    """
    prompt = CLASSIFICATION_PROMPT.format(user_input=user_input)

    # Use groq_chat (raw text) so we can run our own JSON extractor
    raw_response = groq_chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "Return ONLY the JSON object described. "
                    "No markdown fences, no prose, no explanation."
                )
            },
            {"role": "user", "content": prompt},
        ],
        model=MODEL,
        temperature=0.0,
        max_tokens=512,
    )

    return extract_json_from_response(raw_response)


# ─────────────────────────────────────────────
#  SECOND-PASS VERIFIER
#  Called for medium-confidence classifications
# ─────────────────────────────────────────────

VERIFICATION_PROMPT = """\
A classifier labeled this user input as "{first_classification}" with {confidence} confidence.

Re-examine the input independently and confirm or correct the classification.

The ONLY valid classifications are:
  agent_building      = user is DIRECTLY REQUESTING something to be built right now
  conversational      = user is asking a question or seeking knowledge
  needs_clarification = input is too vague to determine

Return ONLY this JSON — no other text:
{{
  "classification": "agent_building" or "conversational" or "needs_clarification",
  "agrees_with_first": true or false,
  "reason": "one sentence"
}}

User Input: {user_input}
"""

def verify_classification(user_input: str, first_result: dict) -> str:
    """
    Second LLM pass for medium-confidence results.
    If both passes agree → use that classification.
    If they disagree → default to needs_clarification.
    """
    first_cls   = first_result.get("classification", "conversational")
    confidence  = first_result.get("confidence", "medium")

    raw = groq_chat(
        messages=[
            {"role": "system", "content": "Return ONLY the JSON object. No prose."},
            {"role": "user",   "content": VERIFICATION_PROMPT.format(
                first_classification=first_cls,
                confidence=confidence,
                user_input=user_input,
            )},
        ],
        model=MODEL,
        temperature=0.0,
        max_tokens=256,
    )

    parsed = extract_json_from_response(raw)
    agrees = parsed.get("agrees_with_first", False)
    second_cls = parsed.get("classification", "needs_clarification")

    if agrees:
        logger.info("Second pass agrees: %s", first_cls)
        return first_cls
    else:
        logger.info("Second pass disagrees: %s → %s → using needs_clarification", first_cls, second_cls)
        # If both passes give different answers, the safest route is clarification
        return "needs_clarification"


# ─────────────────────────────────────────────
#  MAIN AGENT
# ─────────────────────────────────────────────

def perspective_agent(user_input: str) -> Dict[str, Any]:
    """
    Perspective Extractor Agent — main entry point.

    Pipeline:
      0. Validate input (no silent modification)
      1. Pre-classify with rules (zero LLM cost)
      2. If ambiguous → LLM classification
      3. If medium confidence → second LLM pass (verification)
      4. Route: agent_building | conversational | needs_clarification

    Returns dict with keys:
      route, classification, user_text,
      conversational_response, confidence, reason, original_input
    """

    logger.info("─" * 60)
    logger.info("Perspective Agent received input (%d chars)", len(user_input))

    # ── Step 0: Validate ──────────────────────────────────────────
    user_input = validate_input(user_input)
    original   = user_input

    # ── Step 1: Pre-classify (rule-based, zero cost) ───────────────
    pre_result = pre_classify(user_input)

    if pre_result == "injection_blocked":
        return {
            "route":                   "blocked",
            "classification":          "blocked",
            "user_text":               user_input,
            "conversational_response": "I can't process that request as it appears to contain instructions to override system behavior.",
            "confidence":              "high",
            "reason":                  "Prompt injection pattern detected.",
            "original_input":          original,
        }

    if pre_result in ("agent_building", "conversational"):
        classification = pre_result
        confidence     = "high"
        reason         = f"Rule-based pre-classifier matched: {pre_result}"
        logger.info("Pre-classifier result: %s (high confidence)", classification)
    else:
        # ── Step 2: LLM classification ─────────────────────────────
        logger.info("Pre-classifier inconclusive → calling LLM ...")
        llm_result     = llm_classify(user_input)
        classification = llm_result.get("classification", "needs_clarification").lower().strip()
        confidence     = llm_result.get("confidence",     "medium").lower().strip()
        reason         = llm_result.get("reason",         "No reason provided.")
        user_input     = llm_result.get("user_text",      user_input).strip() or user_input

        # Validate classification value
        if classification not in ("agent_building", "conversational", "needs_clarification"):
            logger.warning("Unknown classification '%s' → defaulting to needs_clarification", classification)
            classification = "needs_clarification"
            confidence     = "low"

        # Validate confidence value
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        logger.info("LLM result: %s (confidence: %s)", classification.upper(), confidence)
        logger.info("Reason: %s", reason)

        # ── Step 3: Second-pass verification for medium confidence ──
        if confidence == "medium" and classification != "needs_clarification":
            logger.info("Medium confidence → running second-pass verification ...")
            classification = verify_classification(user_input, llm_result)
            if classification == "needs_clarification":
                confidence = "low"
                reason     = "First and second classification passes disagreed — asking for clarification."

    logger.info("Final classification: %s", classification.upper())

    # ── Step 4: Route ──────────────────────────────────────────────

    # PATH A: Agent Building
    if classification == "agent_building":
        logger.info("Route → JSON Extractor Agent (agent_building)")
        return {
            "route":                   "json_extractor",
            "classification":          "agent_building",
            "user_text":               user_input,
            "conversational_response": None,
            "confidence":              confidence,
            "reason":                  reason,
            "original_input":          original,
        }

    # PATH B: Needs Clarification
    if classification == "needs_clarification" or confidence == "low":
        logger.info("Route → Clarification (ambiguous/low confidence)")
        clarification_response = groq_chat(
            messages=[
                {"role": "system", "content": "You are a friendly AI assistant. Be concise."},
                {"role": "user",   "content": CLARIFICATION_PROMPT.format(user_input=user_input)},
            ],
            model=MODEL,
            temperature=0.4,
            max_tokens=150,
        )
        return {
            "route":                   "clarification",
            "classification":          "needs_clarification",
            "user_text":               user_input,
            "conversational_response": clarification_response,
            "confidence":              confidence,
            "reason":                  reason,
            "original_input":          original,
        }

    # PATH C: Conversational
    logger.info("Route → Code Interface Agent (conversational)")
    conv_response = groq_chat(
        messages=[
            {"role": "system", "content": "Answer clearly and concisely. Do not hallucinate."},
            {"role": "user",   "content": CONVERSATIONAL_PROMPT.format(user_input=user_input)},
        ],
        model=MODEL,
        temperature=0.7,
        max_tokens=700,
    )
    return {
        "route":                   "code_interface",
        "classification":          "conversational",
        "user_text":               user_input,
        "conversational_response": conv_response,
        "confidence":              confidence,
        "reason":                  reason,
        "original_input":          original,
    }


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

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

    user_input = rows[-1]["user_input"]
    preview    = user_input[:80] + ("..." if len(user_input) > 80 else "")
    print(f'\nRead input from {csv_path}: "{preview}"')

    try:
        result = perspective_agent(user_input)

        route_to_file = {
            "json_extractor": os.getenv("BUILD_AGENT_OUTPUT_PATH",      "build_agent_output.json"),
            "code_interface": os.getenv("CONVERSATIONAL_OUTPUT_PATH",    "conversational_output.json"),
            "clarification":  os.getenv("CLARIFICATION_OUTPUT_PATH",     "conversational_output.json"),
            "blocked":        os.getenv("BLOCKED_OUTPUT_PATH",           "conversational_output.json"),
        }
        output_file = route_to_file.get(result["route"], "conversational_output.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        route_emoji = {
            "json_extractor": "🔨",
            "code_interface": "💬",
            "clarification":  "❓",
            "blocked":        "🚫",
        }.get(result["route"], "→")

        print(f"\n{route_emoji} Route      : {result['route']}")
        print(f"   Classification: {result['classification'].upper()}")
        print(f"   Confidence    : {result['confidence']}")
        print(f"   Reason        : {result['reason']}")
        print(f"\n✅ Output saved to {output_file}")

    except (ValueError, RuntimeError) as exc:
        print(f"\n⚠  Error: {exc}")
