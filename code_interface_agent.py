"""
code_interface_agent.py

Reads the generated_agent folder (agent.py, main.py, README.md, requirements.txt),
analyzes them using Groq, and produces a disciplined output.md
that includes file summaries and step-by-step run instructions.

Usage:
    python code_interface_agent.py
    python code_interface_agent.py --folder ./generated_agent
    python code_interface_agent.py --folder ./generated_agent --output output.md
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

from groq_utils import DEFAULT_GROQ_MODEL, groq_chat

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MODEL_NAME = DEFAULT_GROQ_MODEL
EXPECTED_FILES    = ["agent.py", "main.py", "README.md", "requirements.txt"]
DEFAULT_FOLDER    = "./generated_agent"
DEFAULT_OUTPUT    = "output.md"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def read_folder(folder_path: str) -> dict:
    """
    Read all EXPECTED_FILES from folder_path.
    Returns a dict: {filename: content}.
    Warns (does not crash) if a file is missing.
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder_path}")
        sys.exit(1)

    contents = {}
    for fname in EXPECTED_FILES:
        fpath = folder / fname
        if fpath.exists():
            try:
                contents[fname] = fpath.read_text(encoding="utf-8")
                print(f"  [✓] Read  {fname}  ({len(contents[fname])} chars)")
            except Exception as e:
                print(f"  [✗] Could not read {fname}: {e}")
        else:
            print(f"  [!] Missing expected file: {fname}")

    if not contents:
        print("[ERROR] No files could be read from the folder.")
        sys.exit(1)

    return contents


# ─────────────────────────────────────────────
# ANALYSIS TASKS
# ─────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a senior software engineer reviewing an AI agent project. "
    "Be precise, concise, and technical. Do NOT hallucinate. "
    "If something is unclear from the code, say so explicitly."
)


def analyze_file(filename: str, content: str) -> str:
    """Ask Groq to summarize a single file."""
    prompt = f"""Analyze the following file from an AI agent project.

File: {filename}
---
{content}
---

Provide:
1. Purpose of this file (1-2 sentences)
2. Key classes / functions / variables defined (bullet list)
3. External dependencies used (if any)
4. Any notable logic or design patterns observed
"""
    print(f"  → Analyzing {filename} with {MODEL_NAME} ...")
    return groq_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=MODEL_NAME,
        temperature=0.2,
        max_tokens=900,
    )


def generate_run_instructions(files: dict) -> str:
    """Ask Groq to produce step-by-step run instructions."""
    req_content    = files.get("requirements.txt", "Not provided.")
    readme_content = files.get("README.md", "Not provided.")
    main_content   = files.get("main.py", "Not provided.")

    prompt = f"""Based on the following project files, generate clear, step-by-step instructions
to set up and run this AI agent from scratch on a Linux/macOS machine.

requirements.txt:
{req_content}

README.md:
{readme_content}

main.py:
{main_content}

Instructions must include:
1. Prerequisites (Python version, OS, any services needed)
2. Installation steps (virtual environment, pip install)
3. Configuration / environment variables (if any)
4. How to run the agent (exact commands)
5. Expected output / behaviour
6. How to stop / clean up

Use numbered steps and code blocks where appropriate.
"""
    print(f"  → Generating run instructions ...")
    return groq_chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=MODEL_NAME,
        temperature=0.2,
        max_tokens=1000,
    )


# ─────────────────────────────────────────────
# MARKDOWN REPORT BUILDER
# ─────────────────────────────────────────────

def build_markdown_report(
    folder_path: str,
    files: dict,
    file_analyses: dict,
    run_instructions: str,
) -> str:
    """Assemble the final markdown document."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_list_md = "\n".join(f"- `{f}`" for f in files)

    # Per-file sections
    file_sections = ""
    for fname, analysis in file_analyses.items():
        raw_content = files[fname]
        # Detect language for syntax highlighting
        ext = Path(fname).suffix.lstrip(".")
        lang_map = {"py": "python", "md": "markdown", "txt": "text", "json": "json"}
        lang = lang_map.get(ext, "text")

        file_sections += f"""
---

## 📄 `{fname}`

### AI Analysis

{analysis}

### Raw Source

```{lang}
{raw_content}
```
"""

    report = f"""# 🤖 AI Agent Code Interface Report

> **Generated:** {now}  
> **Source Folder:** `{folder_path}`  
> **Analysis Model:** `{MODEL_NAME}` via Groq  

---

## 📁 Files Detected

{file_list_md}

---

## 🚀 How to Run This Agent

{run_instructions}

---

## 🔍 Per-File Analysis & Source Code

{file_sections}

---

*Report generated by `code_interface_agent.py` using model `{MODEL_NAME}`.*
"""
    return report


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Read a generated_agent folder and produce an AI-powered output.md"
    )
    parser.add_argument(
        "--folder",
        default=DEFAULT_FOLDER,
        help=f"Path to the generated_agent folder (default: {DEFAULT_FOLDER})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Code Interface Agent  —  powered by", MODEL_NAME)
    print("=" * 60)

    # 1. Read files
    print(f"\n[1/2] Reading files from: {args.folder}")
    files = read_folder(args.folder)
    print(f"      {len(files)} file(s) loaded ✓")

    # 2. Analyze each file + generate run instructions
    print(f"\n[2/2] Analyzing individual files ...")
    file_analyses = {}
    for fname, content in files.items():
        file_analyses[fname] = analyze_file(fname, content)
    print("      File analysis complete ✓")

    print(f"\n[2/2] Generating run instructions ...")
    run_instructions = generate_run_instructions(files)
    print("      Run instructions complete ✓")

    # Build & write report
    print(f"\n[✍] Building report ...")
    report_md = build_markdown_report(
        folder_path=args.folder,
        files=files,
        file_analyses=file_analyses,
        run_instructions=run_instructions,
    )

    output_path = Path(args.output)
    output_path.write_text(report_md, encoding="utf-8")

    print("=" * 60)
    print(f"  ✅  Report saved to: {output_path.resolve()}")
    print(f"      Total size     : {len(report_md):,} characters")
    print("=" * 60)


if __name__ == "__main__":
    main()
