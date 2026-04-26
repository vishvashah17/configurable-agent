import json
import os
import re
from typing import Dict, List

from dotenv import find_dotenv, load_dotenv
from groq import Groq


# Load local environment (e.g., GROQ_API_KEY in .env) as early as possible.
# `override=True` ensures a stale OS env var doesn't shadow a freshly-updated .env.
load_dotenv(dotenv_path=find_dotenv(), override=True)


DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def require_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file or set it in your environment."
        )
    return key


def groq_client() -> Groq:
    return Groq(api_key=require_groq_api_key())


def _extract_first_json_object(text: str) -> str:
    """
    Best-effort extraction of a JSON object from a model response that may contain
    extra prose or code fences.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty model response")

    # Strip code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        raw = raw.strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    # Fast path: exact JSON
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass

    # Extract first {...} block
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        candidate = match.group(0)
        # Tolerate common "almost JSON" issues from LLMs (e.g., trailing commas)
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        json.loads(fixed)  # validate
        return fixed

    raise ValueError("Could not find a JSON object in model response")


def groq_chat(
    *,
    messages: List[Dict[str, str]],
    model: str = DEFAULT_GROQ_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> str:
    client = groq_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def groq_chat_json(
    *,
    system: str,
    user: str,
    model: str = DEFAULT_GROQ_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> dict:
    text = groq_chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    json_text = _extract_first_json_object(text)
    return json.loads(json_text)
