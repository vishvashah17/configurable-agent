"""
security_scanner.py — Generated Code Security Scanner (G3)
============================================================
Scans LLM-generated Python code for security risks BEFORE delivery.

This is AgentForge's most unique guardrail — no other system hands
LLM-generated code directly to engineers. This scanner MUST run
after agentbuild.py and before verifier.py.

Layers:
  1. Hardcoded secrets detection     (regex)
  2. Dangerous call detection        (AST walk)
  3. Network exfiltration patterns   (regex)
  4. Filesystem access patterns      (AST walk)
  5. Dependency risk assessment      (package name check)

Usage:
    from security_scanner import scan_generated_code, scan_project

    result = scan_generated_code(code_string, "agent.py")
    full   = scan_project("generated_agent/")
"""

import ast
import os
import re
from typing import Any

from guardrails import log


# ─────────────────────────────────────────────
#  1. HARDCODED SECRETS DETECTION (Regex)
# ─────────────────────────────────────────────

HARDCODED_SECRET_PATTERNS = [
    # Generic secrets in assignment
    (
        re.compile(
            r'(?i)(api[_-]?key|secret[_-]?key|password|token|passwd|pwd|auth[_-]?token)'
            r'\s*=\s*["\'][^"\']{8,}["\']'
        ),
        "Hardcoded secret in assignment",
    ),
    # OpenAI-style keys
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), "OpenAI-style API key"),
    # Groq keys
    (re.compile(r'gsk_[a-zA-Z0-9]{20,}'), "Groq API key"),
    # Bearer tokens hardcoded
    (re.compile(r'(?i)bearer\s+[a-zA-Z0-9\-_.]{20,}'), "Hardcoded Bearer token"),
    # AWS secrets
    (
        re.compile(r'(?i)aws_secret[_a-z]*\s*=\s*["\'][^"\']+["\']'),
        "AWS secret key",
    ),
    # Generic lengthy hex/base64 strings that look like secrets
    (
        re.compile(
            r'(?i)(secret|key|token|password)\s*[:=]\s*["\'][A-Za-z0-9+/=]{32,}["\']'
        ),
        "Long credential-like string",
    ),
]


# ─────────────────────────────────────────────
#  2. DANGEROUS CALL DETECTION (AST)
# ─────────────────────────────────────────────

# (module_or_None, function_name): risk_description
DANGEROUS_CALLS: dict[tuple[str | None, str], str] = {
    # Builtins — arbitrary code execution
    (None, "eval"): "eval() can execute arbitrary code",
    (None, "exec"): "exec() can execute arbitrary code",
    (None, "compile"): "compile() enables dynamic code generation",
    (None, "__import__"): "__import__() enables dynamic module loading",

    # os module — system access
    ("os", "system"): "os.system() runs shell commands",
    ("os", "popen"): "os.popen() opens a pipe to a shell command",
    ("os", "execvp"): "os.execvp() replaces current process",
    ("os", "execve"): "os.execve() replaces current process",

    # subprocess — Popen is more dangerous than run
    ("subprocess", "Popen"): "subprocess.Popen() opens an unmanaged child process",
    ("subprocess", "call"): "subprocess.call() with shell=True is risky",

    # Deserialization — arbitrary code execution via crafted data
    ("pickle", "loads"): "pickle.loads() can execute arbitrary code from serialized data",
    ("pickle", "load"): "pickle.load() can execute arbitrary code from files",
    ("marshal", "loads"): "marshal.loads() can execute arbitrary code",
    ("yaml", "load"): "yaml.load() without Loader is unsafe (use safe_load)",

    # Dynamic import hijacking
    ("importlib", "import_module"): "importlib.import_module() enables dynamic module loading",

    # ctypes — native code access
    ("ctypes", "cdll"): "ctypes.cdll loads native libraries",
    ("ctypes", "CDLL"): "ctypes.CDLL loads native libraries",
}


# ─────────────────────────────────────────────
#  3. NETWORK EXFILTRATION PATTERNS (Regex)
# ─────────────────────────────────────────────

NETWORK_EXFIL_PATTERNS = [
    # Sending data to unknown external endpoints
    (
        re.compile(r'requests\.(post|put|patch)\s*\(\s*["\']https?://(?!api\.)'),
        "HTTP POST/PUT to non-API endpoint",
    ),
    (
        re.compile(r'urllib.*urlopen.*https?://'),
        "urllib opening external URL",
    ),
    # Socket connections
    (
        re.compile(r'socket\.connect\s*\('),
        "Direct socket connection",
    ),
    # SMTP without user awareness
    (
        re.compile(r'smtplib\.SMTP\s*\(\s*["\'][^"\']+["\']'),
        "SMTP server connection — ensure user is aware",
    ),
]


# ─────────────────────────────────────────────
#  4. FILESYSTEM ACCESS PATTERNS (AST)
# ─────────────────────────────────────────────

DANGEROUS_FILE_OPERATIONS = {
    # (module, function): risk
    ("shutil", "rmtree"): "shutil.rmtree() can delete entire directory trees",
    ("os", "rmdir"): "os.rmdir() deletes directories",
    ("os", "unlink"): "os.unlink() deletes files",
    ("os", "remove"): "os.remove() deletes files",
    ("os", "rename"): "os.rename() renames/moves files",
    ("pathlib", "unlink"): "Path.unlink() deletes files",
}


# ─────────────────────────────────────────────
#  5. DEPENDENCY RISK ASSESSMENT
# ─────────────────────────────────────────────

# Known risky or fake packages that typosquatters use
SUSPICIOUS_PACKAGES = {
    "python-openssl",     # typosquat — real is pyOpenSSL
    "python3-dateutil",   # typosquat — real is python-dateutil
    "jeIlyfish",          # look-alike fonts
    "colourama",          # typosquat of colorama
    "nmap",               # network scanning tool
    "paramiko",           # SSH — legitimate but risky if unexpected
    "scapy",              # packet forge tool
    "pwntools",           # exploitation framework
}


def check_requirements(requirements_text: str) -> list[str]:
    """
    Check requirements.txt for suspicious or risky packages.

    Returns list of warnings.
    """
    warnings = []
    for line in requirements_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract package name (before any version specifier)
        pkg = re.split(r'[><=!~\[]', line)[0].strip().lower()
        if pkg in SUSPICIOUS_PACKAGES:
            warnings.append(f"Suspicious package '{pkg}' in requirements.txt")
    return warnings


# ─────────────────────────────────────────────
#  MAIN SCANNER
# ─────────────────────────────────────────────

def scan_generated_code(code: str, filename: str) -> dict[str, Any]:
    """
    Perform a comprehensive security scan on a single generated file.

    Returns:
        {
            "filename":  str,
            "issues":    list[str],    # Hard blocks — must fix
            "warnings":  list[str],    # Soft flags — log and inform
            "clean":     bool,         # True if no issues
        }
    """
    issues: list[str] = []
    warnings: list[str] = []

    # ── 1. Hardcoded secrets ──────────────────────────────────────
    for pattern, label in HARDCODED_SECRET_PATTERNS:
        matches = pattern.findall(code)
        if matches:
            # Truncate matched content for log safety
            sample = str(matches[0])[:30] + "..."
            issues.append(f"[SECRET] {label} detected in {filename}: {sample}")

    # ── 2. AST-based analysis ─────────────────────────────────────
    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            call_id: tuple[str | None, str] | None = None

            # eval("..."), exec("..."), compile("...") — builtin calls
            if isinstance(func, ast.Name):
                call_id = (None, func.id)

            # os.system(...), subprocess.Popen(...) — attribute calls
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                call_id = (func.value.id, func.attr)

            # Check against dangerous call registry
            if call_id and call_id in DANGEROUS_CALLS:
                risk = DANGEROUS_CALLS[call_id]
                lineno = getattr(node, "lineno", "?")
                call_str = f"{call_id[0]}.{call_id[1]}" if call_id[0] else call_id[1]
                issues.append(
                    f"[DANGEROUS_CALL] {call_str}() at line {lineno} in {filename}: {risk}"
                )

            # Check subprocess.run with shell=True specifically
            if (isinstance(func, ast.Attribute)
                    and func.attr == "run"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "subprocess"):
                for kw in node.keywords:
                    if (kw.arg == "shell"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True):
                        lineno = getattr(node, "lineno", "?")
                        issues.append(
                            f"[SHELL_INJECTION] subprocess.run(shell=True) at line {lineno} "
                            f"in {filename} — command injection risk"
                        )

            # Check filesystem danger
            if call_id and call_id in DANGEROUS_FILE_OPERATIONS:
                risk = DANGEROUS_FILE_OPERATIONS[call_id]
                lineno = getattr(node, "lineno", "?")
                warnings.append(
                    f"[FILESYSTEM] {call_id[0]}.{call_id[1]}() at line {lineno} "
                    f"in {filename}: {risk}"
                )

    except SyntaxError:
        # Layer 1 (AST check in verifier) already catches this — skip gracefully
        warnings.append(f"[SYNTAX] Could not parse {filename} for AST analysis")

    # ── 3. Network exfiltration patterns ───────────────────────────
    for pattern, label in NETWORK_EXFIL_PATTERNS:
        if pattern.search(code):
            warnings.append(f"[NETWORK] {label} detected in {filename}")

    # ── 4. Additional string-based checks ──────────────────────────

    # Base64-encoded payloads (potential obfuscation)
    b64_blocks = re.findall(r'["\'][A-Za-z0-9+/]{50,}={0,2}["\']', code)
    if len(b64_blocks) > 3:
        warnings.append(
            f"[OBFUSCATION] {len(b64_blocks)} large base64-like strings in {filename}"
        )

    # Infinite loops without obvious break
    if re.search(r'while\s+True\s*:', code) and 'break' not in code:
        warnings.append(f"[RELIABILITY] `while True` without `break` in {filename}")

    # ── Log results ────────────────────────────────────────────────
    if issues:
        log.security(
            "code_security_issues",
            filename=filename,
            issue_count=len(issues),
            issues=issues[:5],  # Cap log length
        )
    if warnings:
        log.warn(
            "code_security_warnings",
            filename=filename,
            warning_count=len(warnings),
        )

    return {
        "filename": filename,
        "issues": issues,
        "warnings": warnings,
        "clean": len(issues) == 0,
    }


def scan_project(project_dir: str) -> dict[str, Any]:
    """
    Scan all generated project files for security issues.

    Args:
        project_dir: Path to generated_agent/ directory

    Returns:
        {
            "clean":         bool,
            "total_issues":  int,
            "total_warnings": int,
            "files":         dict[filename, scan_result],
            "req_warnings":  list[str],
        }
    """
    results: dict[str, Any] = {}
    total_issues = 0
    total_warnings = 0

    # Scan Python files
    for fname in ["agent.py", "main.py"]:
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                code = f.read()
            scan = scan_generated_code(code, fname)
            results[fname] = scan
            total_issues += len(scan["issues"])
            total_warnings += len(scan["warnings"])

    # Scan requirements.txt
    req_warnings: list[str] = []
    req_path = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            req_text = f.read()
        req_warnings = check_requirements(req_text)
        total_warnings += len(req_warnings)

    all_clean = total_issues == 0

    if not all_clean:
        log.security(
            "project_security_scan_failed",
            total_issues=total_issues,
            total_warnings=total_warnings,
        )
    else:
        log.info(
            "project_security_scan_passed",
            total_issues=0,
            total_warnings=total_warnings,
        )

    return {
        "clean": all_clean,
        "total_issues": total_issues,
        "total_warnings": total_warnings,
        "files": results,
        "req_warnings": req_warnings,
    }


# ─────────────────────────────────────────────
#  AUTO-REMEDIATION HELPERS
# ─────────────────────────────────────────────

def strip_hardcoded_secrets(code: str) -> str:
    """
    Replace detected hardcoded secrets with env-var lookups.
    Falls back to the original code on any error.
    """
    try:
        # Replace api_key = "sk-xxxx" → api_key = os.getenv("API_KEY")
        cleaned = re.sub(
            r'(?i)(api[_-]?key|secret[_-]?key|password|token|auth[_-]?token)'
            r'\s*=\s*["\'][^"\']{8,}["\']',
            r'\1 = os.getenv("\1".upper(), "")',
            code,
        )
        # Replace bare sk-xxxx strings
        cleaned = re.sub(
            r'["\']sk-[a-zA-Z0-9]{20,}["\']',
            'os.getenv("OPENAI_API_KEY", "")',
            cleaned,
        )
        cleaned = re.sub(
            r'["\']gsk_[a-zA-Z0-9]{20,}["\']',
            'os.getenv("GROQ_API_KEY", "")',
            cleaned,
        )
        return cleaned
    except Exception:
        return code


# ─────────────────────────────────────────────
#  CLI ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "generated_agent"
    if os.path.isdir(target):
        result = scan_project(target)
        print(f"\n{'='*50}")
        print(f"  Security Scan: {'PASS ✅' if result['clean'] else 'FAIL ❌'}")
        print(f"  Issues:   {result['total_issues']}")
        print(f"  Warnings: {result['total_warnings']}")
        print(f"{'='*50}\n")
        for fname, scan in result["files"].items():
            if scan["issues"] or scan["warnings"]:
                print(f"\n  {fname}:")
                for i in scan["issues"]:
                    print(f"    ❌ {i}")
                for w in scan["warnings"]:
                    print(f"    ⚠  {w}")
        if result["req_warnings"]:
            print(f"\n  requirements.txt:")
            for w in result["req_warnings"]:
                print(f"    ⚠  {w}")
    elif os.path.isfile(target):
        with open(target, "r", encoding="utf-8") as f:
            code = f.read()
        result = scan_generated_code(code, os.path.basename(target))
        print(f"\n  {target}: {'CLEAN ✅' if result['clean'] else 'ISSUES ❌'}")
        for i in result["issues"]:
            print(f"    ❌ {i}")
        for w in result["warnings"]:
            print(f"    ⚠  {w}")
    else:
        print(f"Path not found: {target}")
        sys.exit(1)
