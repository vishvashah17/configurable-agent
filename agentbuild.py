# agentbuild.py  —  Code Generator Agent
# Strategy: ONE focused Groq call per file (agent.py, main.py, requirements.txt, README.md)
# Why: Asking the model to return 4 files as one escaped JSON string is unreliable.
#      Splitting into 4 focused calls gives clean raw output every time.

import json
import re
import logging
import sys
import os
from typing import Dict, Any

from groq import Groq                          # pip install groq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CodeGeneratorAgent")

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")       # set in your environment or .env
MODEL        = "llama-3.3-70b-versatile"  # best Groq model for code generation
MAX_RETRIES  = 3

# Frameworks — anything not in this list is NOT a web framework
KNOWN_FRAMEWORKS = {"fastapi", "flask", "django", "tornado", "aiohttp", "starlette"}

# Required fields in the spec
REQUIRED_FIELDS = ["agent_name", "primary_purpose", "capabilities", "language"]

# ─────────────────────────────────────────────
#  SYSTEM PROMPTS  (one per file type)
#  Hardened: small models need explicit, repeated constraints to suppress prose.
# ─────────────────────────────────────────────

SYSTEM_AGENT_PY = """\
You are an expert Python architect. Generate production-ready agent code following best practices.

RULES:
- Output RAW Python only. No markdown, no prose.
- Start immediately with import statements or docstrings
- Follow standard Python project structure: imports, constants, class definition, methods
- Every method must have proper docstrings and type hints
- Use descriptive variable names and follow PEP 8 conventions
- Handle errors gracefully with specific exception handling
- Use logging instead of print statements for debugging
- Make code modular and reusable
- Include comprehensive error handling and validation
- Use context managers for resource management
- Follow SOLID principles for class design

STRUCTURE:
1. Standard library imports
2. Third-party imports  
3. Module-level constants/variables
4. Main agent class with proper __init__
5. Capability methods as specified
6. Utility methods
7. Main execution block

Generate complete, working agent.py now:
"""


SYSTEM_MAIN_PY = """\
You are an expert Python developer creating entry points. Generate clean main.py files.

RULES:
- Output RAW Python only. No markdown, no explanations.
- Import the agent class properly from agent.py
- Handle command-line arguments appropriately
- Implement proper error handling and graceful shutdown
- Use argparse for complex parameter handling
- Include logging configuration
- Handle KeyboardInterrupt and other exceptions gracefully
- For web frameworks: configure proper startup/shutdown
- For standalone apps: implement async event loops when needed
- Keep under 50 lines but make it robust

PATTERN:
1. Imports
2. Logging setup
3. Argument parsing (if needed)
4. Main function with error handling
5. if __name__ == '__main__': block

Generate complete main.py now:
"""


SYSTEM_REQUIREMENTS = """\
You are a Python dependency expert. Generate precise requirements.txt files.

RULES:
- List packages one per line with version specifiers
- Use >= for version pinning (e.g., requests>=2.28.0)
- Only include packages actually used in the code
- Pin major versions to avoid breaking changes
- Include python-dotenv>=1.0.0 always
- Sort packages alphabetically
- Use specific versions known to work together
- No comments, no blank lines, no prose

ANALYSIS CHECKLIST:
1. Web frameworks: fastapi, flask, django need their ecosystem
2. Database: psycopg2 for PostgreSQL, pymongo for MongoDB, etc.
3. APIs: requests for HTTP, specific SDKs when mentioned
4. Data processing: pandas, numpy for numerical work
5. AI/ML: transformers, torch, openai, anthropic as needed
6. Utilities: python-dotenv, pydantic, etc.

Generate requirements.txt now:
"""


SYSTEM_README = """\
You are a technical documentation expert. Create comprehensive README.md files.

STRUCTURE:
# [Project Name]
Brief description of what this agent does

## Features
Bullet points of key capabilities

## Prerequisites
What needs to be installed (Python version, system dependencies)

## Installation
Step-by-step setup instructions:
```bash
git clone ...
cd ...
pip install -r requirements.txt
"""

# ─────────────────────────────────────────────
#  USER PROMPT BUILDERS  (one per file)
# ─────────────────────────────────────────────

# ── Capability → library + implementation hints ──────────────────────────────
_CAP_HINTS = {
    "reading csv files"         : "Use the csv module (stdlib): open(path,'r'), csv.DictReader(f) to read rows.",
    "csv"                       : "Use the csv module (stdlib): open(path,'r'), csv.DictReader(f) to read rows.",
    "extracting named entities" : "Use spacy: import spacy; nlp=spacy.load('en_core_web_sm'); doc=nlp(text); iterate doc.ents for ent.text and ent.label_.",
    "named entity"              : "Use spacy: import spacy; nlp=spacy.load('en_core_web_sm'); doc=nlp(text); iterate doc.ents for ent.text and ent.label_.",
    "writing to json"           : "Use json module (stdlib): open(path,'w'), json.dump(data, f, indent=2).",
    "json"                      : "Use json module (stdlib): open(path,'w'), json.dump(data, f, indent=2).",
    "web scraping"              : "Use requests and BeautifulSoup4: requests.get(url), BeautifulSoup(resp.content,'html.parser').",
    "summarization"             : "Use spacy or nltk for extractive summarization.",
    "llm"                       : "Use langchain-ollama: from langchain_ollama import OllamaLLM; llm=OllamaLLM(model='mistral'); llm.invoke(prompt).",
    "pdf"                       : "Use PyPDF2: import PyPDF2; reader=PyPDF2.PdfReader(path); page.extract_text().",
    "email"                     : "Use smtplib and email.mime (stdlib) for sending emails.",
    "file monitoring"           : "Use watchdog: from watchdog.observers import Observer; from watchdog.events import FileSystemEventHandler.",
}

def _get_capability_hints(caps: list, tools: list) -> str:
    """Return concrete library+implementation hints for each capability."""
    all_text = " ".join(c.lower() for c in caps) + " " + " ".join(t.lower() for t in tools)
    hints, seen = [], set()
    for key, hint in _CAP_HINTS.items():
        if key in all_text and hint not in seen:
            hints.append(f"  - {hint}")
            seen.add(hint)
    return "\n".join(hints) if hints else "  - Use standard Python libraries appropriate for the task."


def prompt_agent_py(spec: Dict[str, Any]) -> str:
    caps     = spec.get("capabilities", [])
    lang     = spec.get("language", "Python")
    fw       = spec.get("framework", "none")
    apis     = spec.get("api_integrations", []) or []
    db       = spec.get("database", "none") or "none"
    tools    = spec.get("third_party_tools", []) or []
    ext_apis = spec.get("external_apis", []) or []
    name     = spec.get("agent_name", "Agent")
    purpose  = spec.get("primary_purpose", "")

    framework_line = (
        f"Web framework: {fw}" if fw and fw not in ("none", "null", "")
        else "No web framework — standalone Python class only"
    )

    cap_hints    = _get_capability_hints(caps, tools)
    method_list  = "\n".join(f"  - {c}" for c in caps)

    return f"""\
Generate a complete, working agent.py file.
Output RAW Python ONLY. No markdown. No fences. No prose. Start with the first import line.

=== AGENT SPECIFICATION ===
Agent Name    : {name}
Purpose       : {purpose}
Language      : {lang}
{framework_line}
Capabilities  : {json.dumps(caps)}
External APIs : {json.dumps(apis + ext_apis)}
Database      : {db}
Tools         : {json.dumps(tools)}
Target Users  : {spec.get('target_users', 'general users')}

=== METHODS TO IMPLEMENT (one method per capability) ===
{method_list}

=== LIBRARY HINTS — use these exact approaches ===
{cap_hints}

=== CRITICAL REQUIREMENTS ===
- Every instance variable used in any method MUST be assigned in __init__.
- Fully implement every method — no stubs, no 'pass', no placeholder comments.
- Each import must appear EXACTLY ONCE at the top of the file.
- Include a run() method that calls all capability methods in sequence.
- Include a if __name__ == '__main__': block that creates and runs the agent.

Generate agent.py now:
"""

def prompt_main_py(spec: Dict[str, Any]) -> str:
    fw         = spec.get("framework", "none") or "none"
    agent_name = spec.get("agent_name", "Agent")
    class_name = "".join(
        w.capitalize() for w in re.sub(r"[^a-zA-Z0-9 ]", " ", agent_name).split()
    )

    return f"""\
Generate main.py entry point for this agent.
Output raw Python code ONLY. No explanations. No markdown fences.

Agent class   : {class_name}  (imported from agent.py)
Framework     : {fw}
Agent Purpose : {spec.get('primary_purpose')}

If framework is fastapi  -> run with uvicorn on port 8000
If framework is flask    -> run Flask app on port 8000
Otherwise               -> run with asyncio.run(main())

Generate the complete main.py now. Raw Python only. Start immediately with import.
"""

def prompt_requirements(spec: Dict[str, Any]) -> str:
    caps  = " ".join(c.lower() for c in (spec.get("capabilities") or []))
    fw    = spec.get("framework", "none") or "none"
    db    = (spec.get("database") or "none").lower()
    cloud = (spec.get("cloud_platform") or "none").lower()
    apis  = [a.lower() for a in (spec.get("api_integrations") or [])]
    tools = [t.lower() for t in (spec.get("third_party_tools") or [])]

    hints = []
    if fw in ("fastapi", "fast api"):                     hints.append("fastapi, uvicorn")
    if fw == "flask":                                      hints.append("flask")
    if "postgresql" in db:                                hints.append("psycopg2-binary")
    if "mongodb" in db:                                   hints.append("pymongo")
    if "sqlite" in db:                                    hints.append("aiosqlite")
    if "aws" in cloud:                                    hints.append("boto3")
    if "gcp" in cloud:                                    hints.append("google-cloud")
    if "azure" in cloud:                                  hints.append("azure-core")
    if any(k in caps for k in ("llm", "ai", "chat")):     hints.append("langchain-ollama, langchain-core")
    if any(k in caps for k in ("scrape", "web", "html")): hints.append("requests, beautifulsoup4")
    if "pdf" in caps:                                     hints.append("PyPDF2")
    if "csv" in caps or "csv" in " ".join(tools):         hints.append("pandas")
    if "openai" in apis:                                  hints.append("openai")
    if "anthropic" in apis:                               hints.append("anthropic")
    hints_str = ", ".join(hints) if hints else "none specifically detected"

    return f"""\
Generate requirements.txt for this agent.
Output package list ONLY. No explanations. No comments. No markdown.

Capabilities  : {spec.get('capabilities')}
Framework     : {fw}
Database      : {db}
Cloud         : {cloud}
APIs          : {apis}
Tools         : {tools}
Likely packages needed: {hints_str}
Always include: python-dotenv>=1.0.0

Generate the complete requirements.txt now. Start immediately with the first package name.
"""

def prompt_readme(spec: Dict[str, Any]) -> str:
    return f"""\
Generate README.md for this agent project.

Agent Name    : {spec.get('agent_name')}
Purpose       : {spec.get('primary_purpose')}
Language      : {spec.get('language', 'Python')}
Framework     : {spec.get('framework', 'none')}
Capabilities  : {spec.get('capabilities')}
Database      : {spec.get('database', 'none')}

Include: title, description, prerequisites, installation steps,
how to run, capabilities list, example usage.
This file is the ONLY place for explanations, design notes, and usage guidance.

Generate the complete README.md now.
"""

# ─────────────────────────────────────────────
#  SPEC VALIDATOR & NORMALIZER
# ─────────────────────────────────────────────

def validate_and_normalize(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate required fields exist and normalize all values.
    Raises ValueError on bad input.
    """
    if not isinstance(spec, dict):
        raise ValueError("Spec must be a dict.")

    missing = [f for f in REQUIRED_FIELDS if not spec.get(f)]
    if missing:
        raise ValueError(f"Spec missing required fields: {missing}")

    s = spec.copy()

    # Normalize list fields
    for field in ["capabilities", "api_integrations", "content_types",
                  "third_party_tools", "external_apis", "internal_systems",
                  "database_connections", "personality"]:
        val = s.get(field)
        if isinstance(val, str):
            s[field] = [val] if val else []
        elif val is None:
            s[field] = []

    # Normalize string fields
    for field in ["agent_name", "primary_purpose", "language", "framework",
                  "database", "cloud_platform", "tone", "domain"]:
        val = s.get(field)
        s[field] = str(val).strip() if val else ""

    # Fix framework: if it's a library name (pandas, numpy etc.) not a web framework
    fw = s.get("framework", "").lower()
    if fw and fw not in KNOWN_FRAMEWORKS:
        logger.warning(
            "framework='%s' is not a web framework — treating as a tool/library. "
            "Moving to third_party_tools, setting framework=none.", fw
        )
        if fw not in [t.lower() for t in s["third_party_tools"]]:
            s["third_party_tools"].append(s["framework"])
        s["framework"] = "none"

    return s

# ─────────────────────────────────────────────
#  GROQ CALLER  (replaces call_ollama)
# ─────────────────────────────────────────────

def call_groq(system_prompt: str, user_prompt: str, label: str) -> str:
    """
    One focused call to Groq for a single file.
    Returns raw text. No JSON parsing needed.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it with: export GROQ_API_KEY=your_key_here"
        )

    client = Groq(api_key=GROQ_API_KEY)

    try:
        logger.info("Generating %s ...", label)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise RuntimeError(f"Empty response for {label}")
        logger.info("%s done (%d chars)", label, len(content))
        return content

    except RuntimeError:
        raise
    except Exception as e:
        # Preserve the original error type name for clarity
        raise RuntimeError(f"Groq API error for {label}: {type(e).__name__}: {e}") from e

# ─────────────────────────────────────────────
#  CODE CLEANER
# ─────────────────────────────────────────────

# Prose patterns that small models emit before or after code
_PROSE_LINE_RE = re.compile(
    r"^("
    r"sure[,!.]|here('s| is)|certainly|of course|below (is|you'll find)|"
    r"this (is|code|script|file|implements|will|shows)|"
    r"the (above|following|code|script|file)|"
    r"i (have|will|can|hope)|note that|please|as requested|"
    r"explanation|output:|result:|---+|===+"
    r")",
    re.IGNORECASE,
)

def _deduplicate_imports(code: str) -> str:
    """
    Remove duplicate import statements, keeping only the first occurrence.
    Also strips inline linter comments (# noqa, # type: ignore) from import lines.
    """
    seen: set = set()
    result = []
    for line in code.splitlines():
        stripped = line.strip()
        is_import = bool(re.match(r"^(import |from \S+ import )", stripped))
        if is_import:
            clean_line = re.sub(r"\s*#.*$", "", line).rstrip()
            key = clean_line.strip()
            if key in seen:
                continue
            seen.add(key)
            result.append(clean_line)
        else:
            result.append(line)
    return "\n".join(result)


def clean_output(raw: str, file_type: str) -> str:
    """
    Strip markdown fences, preamble prose, trailing commentary,
    and duplicate imports from raw model output.
    """
    # 1. Strip markdown fences
    cleaned = re.sub(r"^```[\w]*\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # ── requirements.txt ──────────────────────────────────────────────
    if file_type == "requirements.txt":
        lines = []
        for line in cleaned.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and re.match(r"^[a-zA-Z0-9_\-\.]+", line):
                lines.append(line)
        return "\n".join(lines) + "\n"

    # ── Python files ──────────────────────────────────────────────────
    if file_type in ("agent.py", "main.py"):
        # Drop prose lines before first real code line
        code_lines = cleaned.splitlines()
        start_idx = 0
        for i, line in enumerate(code_lines):
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^(import |from |class |def |#|\"\"\")", stripped):
                start_idx = i
                break
        cleaned = "\n".join(code_lines[start_idx:])

        # Drop trailing prose after last code line
        lines = cleaned.splitlines()
        last_code = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if not stripped:
                continue
            if re.match(r"^[ \t]|^[a-zA-Z_\"'#@]", stripped):
                last_code = i + 1
                break
            if _PROSE_LINE_RE.match(stripped):
                continue
            last_code = i + 1
            break
        cleaned = "\n".join(lines[:last_code])

        # Deduplicate imports and strip linter noise
        cleaned = _deduplicate_imports(cleaned)

        # Remove accidental secrets
        cleaned = re.sub(
            r'(sk-[a-zA-Z0-9]{20,}|api[_-]?key\s*=\s*["\'][^"\']{8,}["\'])',
            "os.getenv('API_KEY')",
            cleaned,
            flags=re.IGNORECASE,
        )

    return cleaned.strip() + "\n"


def validate_output(files: Dict[str, str]) -> None:
    """
    Sanity-check generated files and log warnings for any issues found.
    Does NOT raise — the user still gets output even if imperfect.
    """
    agent_code = files.get("agent.py", "")

    if "class " not in agent_code:
        logger.warning("VALIDATION: agent.py has no class definition.")
    if "def __init__" not in agent_code:
        logger.warning("VALIDATION: agent.py has no __init__ method.")

    for fname in ("agent.py", "main.py"):
        code = files.get(fname, "")
        import_lines = [
            re.sub(r"\s*#.*$", "", l).strip()
            for l in code.splitlines()
            if re.match(r"^\s*(import |from \S+ import )", l)
        ]
        dupes = [l for l in import_lines if import_lines.count(l) > 1]
        if dupes:
            logger.warning("VALIDATION: %s still has duplicate imports: %s", fname, list(set(dupes)))

    init_match = re.search(r"def __init__\(.*?\n(?=    def |\Z)", agent_code, re.DOTALL)
    if init_match:
        assigned     = set(re.findall(r"self\.(\w+)\s*=", init_match.group()))
        all_used     = set(re.findall(r"self\.(\w+)", agent_code))
        method_names = set(re.findall(r"def (\w+)\(self", agent_code))
        unassigned   = all_used - assigned - method_names - {"__class__", "__dict__"}
        if unassigned:
            logger.warning(
                "VALIDATION: self.%s used but not assigned in __init__ — will cause AttributeError.",
                ", self.".join(sorted(unassigned))
            )

    req = files.get("requirements.txt", "").strip()
    if not req:
        logger.warning("VALIDATION: requirements.txt is empty.")
    else:
        logger.info("VALIDATION: requirements.txt has %d packages.", len([l for l in req.splitlines() if l.strip()]))

    logger.info("VALIDATION complete.")

# ─────────────────────────────────────────────
#  RETRY WRAPPER
# ─────────────────────────────────────────────

def generate_with_retry(system_prompt: str, user_prompt: str, label: str) -> str:
    """Call Groq with retry on runtime errors."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return call_groq(system_prompt, user_prompt, label)
        except RuntimeError as e:
            logger.warning("Attempt %d/%d for %s failed: %s", attempt, MAX_RETRIES, label, e)
            last_err = e
    raise RuntimeError(
        f"Failed to generate {label} after {MAX_RETRIES} attempts: {last_err}"
    )

# ─────────────────────────────────────────────
#  MAIN AGENT CLASS
# ─────────────────────────────────────────────

class CodeGeneratorAgent:
    """
    Generates a complete agent project (4 files) from an agent spec dict.
    Makes one focused Groq call per file for reliability.
    """

    def generate(self, raw_spec: Dict[str, Any]) -> Dict[str, str]:
        """
        Args:
            raw_spec: Agent spec dict from inputextractor.py

        Returns:
            { 'agent.py', 'main.py', 'requirements.txt', 'README.md' }

        Raises:
            ValueError, RuntimeError
        """
        logger.info("Validating agent spec ...")
        spec = validate_and_normalize(raw_spec)
        logger.info(
            "Spec valid. Agent: '%s' | Language: %s | Framework: %s | Caps: %s",
            spec["agent_name"], spec["language"],
            spec["framework"], spec["capabilities"]
        )

        files = {}

        # 1. agent.py
        raw = generate_with_retry(SYSTEM_AGENT_PY, prompt_agent_py(spec), "agent.py")
        files["agent.py"] = clean_output(raw, "agent.py")

        # 2. main.py
        raw = generate_with_retry(SYSTEM_MAIN_PY, prompt_main_py(spec), "main.py")
        files["main.py"] = clean_output(raw, "main.py")

        # 3. requirements.txt
        raw = generate_with_retry(SYSTEM_REQUIREMENTS, prompt_requirements(spec), "requirements.txt")
        files["requirements.txt"] = clean_output(raw, "requirements.txt")

        # 4. README.md
        raw = generate_with_retry(SYSTEM_README, prompt_readme(spec), "README.md")
        files["README.md"] = clean_output(raw, "README.md")

        logger.info("All files generated: %s", list(files.keys()))
        validate_output(files)
        return files


# ─────────────────────────────────────────────
#  PUBLIC API  (used by pipeline / UI)
# ─────────────────────────────────────────────

def run_code_generator(spec: Dict[str, Any]) -> Dict[str, str]:
    """Convenience wrapper for the pipeline."""
    return CodeGeneratorAgent().generate(spec)


# ─────────────────────────────────────────────
#  CLI ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Accept spec path from argument, or try default filenames
    if len(sys.argv) > 1:
        spec_path = sys.argv[1]
    elif os.path.exists("final_agent.json"):
        spec_path = "final_agent.json"
    else:
        print("Spec file not found. Tried: final_agent.json")
        print("Usage: python agentbuild.py <path_to_spec.json>")
        sys.exit(1)

    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    logger.info("Loaded spec from %s", spec_path)

    try:
        files = run_code_generator(spec)

        output_dir = "generated_agent"
        os.makedirs(output_dir, exist_ok=True)

        print("\n── Generated Files ──")
        for filename, content in files.items():
            out_path = os.path.join(output_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  ✓  {out_path}  ({len(content)} chars)")

        print(f"\n✅ Agent project saved to ./{output_dir}/")
        print(f"   Next: cd {output_dir} && pip install -r requirements.txt && python main.py")

    except (ValueError, RuntimeError) as e:
        print(f"\n⚠  Error: {e}")
        sys.exit(1)