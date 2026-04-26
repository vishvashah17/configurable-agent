# AgentForge — Detailed Project Workflow & Architecture

> **Configuration-Driven Agentic System**
> Generate production-ready AI agents from natural language prompts.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project File Inventory](#2-project-file-inventory)
3. [Technology Stack](#3-technology-stack)
4. [Authentication System](#4-authentication-system)
5. [Pipeline Workflow — Step by Step](#5-pipeline-workflow--step-by-step)
6. [Backend Agent Modules — Deep Dive](#6-backend-agent-modules--deep-dive)
7. [Server Orchestration (server.py)](#7-server-orchestration-serverpy)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Data Flow Diagram](#9-data-flow-diagram)
10. [Artifact Files & Intermediate Outputs](#10-artifact-files--intermediate-outputs)
11. [Retry & Regeneration Logic](#11-retry--regeneration-logic)
12. [Scoring & Verification System](#12-scoring--verification-system)
13. [CLI Entry Point (main.py)](#13-cli-entry-point-mainpy)
14. [Environment & Configuration](#14-environment--configuration)
15. [Security Considerations](#15-security-considerations)

---

## 1. System Overview

AgentForge is a **configuration-driven agentic system** that converts natural language prompts into fully functional Python agent projects. The system uses an LLM-powered multi-agent pipeline where each agent performs a specialized role:

```
User Prompt → Classify → Extract Spec → [User Confirms JSON] → Generate Code → Verify → Deliver
```

The system has **two entry points**:

| Entry Point | Command | Interface |
|-------------|---------|-----------|
| **Web UI** | `python server.py` | Browser at `http://localhost:5000` |
| **CLI** | `python main.py` | Terminal with colored output |

Both execute the same 4-step pipeline but through different orchestration layers.

---

## 2. Project File Inventory

### Backend Agents (Python)

| File | Role | Lines | LLM Calls |
|------|------|-------|-----------|
| `perspective_agent.py` | Classify input as "agent_building" or "conversational" | 352 | 1–2 |
| `inputextractor.py` | Extract structured agent spec from natural language | 426 | 5 |
| `agentbuild.py` | Generate `agent.py`, `main.py`, `requirements.txt`, `README.md` | 655 | 4 |
| `verifier.py` | 3-layer verification (Syntax + Compliance + LLM) | 384 | 1 |

### Infrastructure

| File | Role |
|------|------|
| `server.py` | Flask web server — REST API + static frontend + pipeline orchestration |
| `auth.py` | SQLite-backed authentication — signup, login, HMAC-signed tokens |
| `groq_utils.py` | Shared Groq API client, JSON extractor, error handling |
| `main.py` | CLI pipeline orchestrator with colored terminal output |
| `code_interface_agent.py` | Markdown documentation generator for generated agent folders |

### Frontend

| File | Role |
|------|------|
| `frontend/index.html` | App shell — auth overlay + main pipeline UI |
| `frontend/style.css` | Premium dark theme — glassmorphism, animations, custom scrollbar |
| `frontend/app.js` | Client-side logic — auth flow, polling, pipeline visualization |

### Configuration & Data

| File | Role |
|------|------|
| `.env` | Environment variables (`GROQ_API_KEY`, `AUTH_SECRET_KEY`) |
| `requirements.txt` | Python dependencies for the system itself |
| `agentforge.db` | SQLite database for user accounts and sessions |
| `input.csv` | Append-only log of all user prompts with timestamps |

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **LLM** | Groq Cloud API | All AI reasoning (classification, extraction, generation, verification) |
| **Model** | `llama-3.3-70b-versatile` | Primary model for all LLM calls |
| **Backend** | Python 3.10+ | All agent scripts and server |
| **Web Server** | Flask 3.x + Flask-CORS | REST API + static file serving |
| **Database** | SQLite 3 | User authentication and session storage |
| **Auth** | PBKDF2-HMAC-SHA256 + HMAC tokens | Password hashing + session tokens |
| **Frontend** | Vanilla HTML/CSS/JS | No framework — pure DOM manipulation |
| **Fonts** | Inter + JetBrains Mono | UI and code display |

### Python Dependencies

```
flask>=3.0.0
flask-cors>=4.0.0
groq>=0.9.0
python-dotenv>=1.0.0
```

> **Note:** `auth.py` uses only Python stdlib (`hashlib`, `hmac`, `sqlite3`, `base64`) — no extra auth packages needed.

---

## 4. Authentication System

### Architecture

```
┌──────────┐     POST /api/auth/signup     ┌──────────┐
│  Browser │ ─────────────────────────────▶ │ server.py│
│          │     POST /api/auth/login      │          │
│ (app.js) │ ─────────────────────────────▶ │  auth.py │ ──▶ agentforge.db
│          │     GET  /api/auth/me         │          │
│          │ ─────────────────────────────▶ │          │
└──────────┘                               └──────────┘
```

### Database Schema (`agentforge.db`)

**`users` table:**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `username` | TEXT | NOT NULL, UNIQUE, CASE-INSENSITIVE |
| `email` | TEXT | NOT NULL, UNIQUE, CASE-INSENSITIVE |
| `password` | TEXT | PBKDF2-HMAC-SHA256 hash (hex) |
| `salt` | TEXT | Random 16-byte hex salt per user |
| `created_at` | TEXT | Auto-set to `datetime('now')` |
| `last_login` | TEXT | Updated on each login |

**`sessions` table:**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `user_id` | INTEGER | FOREIGN KEY → users(id) ON DELETE CASCADE |
| `token` | TEXT | UNIQUE HMAC-signed token |
| `created_at` | TEXT | Auto-set |
| `expires_at` | TEXT | Token expiry (default: 72 hours) |

### Token Format

Tokens are **not JWT** but use the same principle:
```
<base64url-encoded-payload>.<hmac-sha256-signature>
```

**Payload:** `{"uid": 1, "usr": "vishva", "exp": 1745900000}`

### Auth Flow

1. **Signup**: `POST /api/auth/signup` → creates user → auto-logs-in → returns token
2. **Login**: `POST /api/auth/login` → verifies PBKDF2 hash → creates session → returns token
3. **Auth Check**: `GET /api/auth/me` with `Authorization: Bearer <token>` → returns user info
4. **Protected Routes**: `/api/generate` and `/api/confirm/<id>` require `@require_auth` decorator
5. **Logout**: `POST /api/auth/logout` → deletes session from DB
6. **Client Storage**: Token stored in `localStorage` as `agentforge_token`
7. **Auto-login**: On page load, `tryAutoLogin()` checks stored token via `/api/auth/me`

### Password Security

- **Algorithm**: PBKDF2-HMAC-SHA256
- **Iterations**: 100,000
- **Salt**: 16 random bytes per user (via `secrets.token_hex(16)`)
- **Comparison**: `hmac.compare_digest()` (constant-time, prevents timing attacks)

---

## 5. Pipeline Workflow — Step by Step

The pipeline has **4 steps** with a **user confirmation gate** between Steps 2 and 3:

```
┌─────────┐    ┌─────────────┐    ┌──────────────────┐    ┌───────────┐    ┌──────────┐
│  Step 1  │───▶│   Step 2     │───▶│  CONFIRMATION    │───▶│  Step 3   │───▶│  Step 4  │
│Perspective│   │ Extractor    │   │     GATE         │   │  Builder  │   │ Verifier │
│  Agent   │   │              │   │ User reviews and │   │           │   │          │
│          │   │              │   │ edits JSON spec  │   │           │   │          │
└─────────┘   └─────────────┘   └──────────────────┘   └───────────┘   └──────────┘
     │               │                   │                    │               │
     ▼               ▼                   ▼                    ▼               ▼
input.csv →    build_agent_      final_agent.json      generated_agent/  verifier_result.json
               output.json       (user-confirmed)      ├── agent.py
               OR                                      ├── main.py
               conversational_                         ├── requirements.txt
               output.json                             └── README.md
```

### Step 1: Perspective Agent (`perspective_agent.py`)

**Purpose:** Classify the user's input to determine the pipeline route.

**Process:**
1. Read the latest row from `input.csv`
2. Validate input (3–5000 chars, basic sanitization)
3. Send classification prompt to Groq LLM
4. Parse response as JSON with 4-level fallback strategy
5. Route decision:
   - **`agent_building`** → save to `build_agent_output.json` → continue pipeline
   - **`conversational`** → generate conversational response → save to `conversational_output.json` → pipeline stops (Steps 2–4 skipped)

**LLM Call:** 1 call for classification + 1 optional call for conversational response

**Output files:**
- `build_agent_output.json` — if agent-building route
- `conversational_output.json` — if conversational route

**Classification criteria:**
- "Build me...", "Create...", "Make...", "Generate..." → `agent_building`
- "What is...", "How does...", "Explain..." → `conversational`
- Ambiguous + any hint of building → defaults to `agent_building`

---

### Step 2: Input Extractor (`inputextractor.py`)

**Purpose:** Extract a structured agent specification from the user's natural language prompt.

**Process:**
1. Read the latest prompt from `input.csv`
2. Make **5 parallel LLM calls** to extract different specification categories:

| Call # | Category | Extracts |
|--------|----------|----------|
| 1 | `core_specifications` | Agent name, purpose, capabilities, target users, domain, content types, decision authority |
| 2 | `language_selection` | Best programming language + reasoning |
| 3 | `technical_requirements` | Language, framework, APIs, database, cloud, performance, security, storage, memory, tools |
| 4 | `behavioral_traits` | Tone, personality, emotional intelligence |
| 5 | `integration_needs` | External APIs, internal systems, database connections |

3. **Language Resolution Priority:**
   - Explicit language from `technical_requirements` (highest)
   - `language_selection` LLM result (middle)
   - Default: `Python` (fallback)

4. Build unified JSON with defaults for empty fields
5. In CLI mode: interactive `confirm_and_edit()` loop
6. In web mode: server auto-confirms with `yes\n` stdin, saves to `final_agent.json`

**Default values (applied when field is empty/null):**

| Field | Default |
|-------|---------|
| `agent_name` | `AutoAgent` |
| `language` | `Python` |
| `framework` | `None` |
| `database` | `json_file` |
| `cloud_platform` | `local` |
| `tone` | `neutral` |
| `personality` | `["helpful"]` |
| `storage` | `json_file` |
| `memory` | `in_memory` |

**Output file:** `final_agent.json`

---

### Confirmation Gate (Web UI Only)

**Purpose:** Let the user review and edit the extracted JSON specification before code generation.

**Process:**
1. Pipeline pauses with `status: "awaiting_confirmation"`
2. Frontend switches to "Spec JSON" tab showing editable JSON textarea
3. User reviews, modifies fields as needed
4. User clicks "Confirm JSON & Generate"
5. Frontend sends `POST /api/confirm/<job_id>` with the edited `agent_spec`
6. Server writes confirmed spec to `final_agent.json`
7. Pipeline resumes with Steps 3–4

**Why this exists:** Prevents wasted LLM tokens on incorrect specifications. The user can fix agent name, capabilities, framework, etc. before code generation begins.

---

### Step 3: Code Generator (`agentbuild.py`)

**Purpose:** Generate a complete, runnable Python project from the confirmed spec.

**Process:**
1. Load and validate `final_agent.json`
2. Normalize the spec:
   - Convert strings to lists where needed
   - Move non-web-framework values from `framework` to `third_party_tools`
   - Known web frameworks: `fastapi`, `flask`, `django`, `tornado`, `aiohttp`, `starlette`
3. Make **4 focused LLM calls** (one per file):

| Call # | File | System Prompt Focus | Max Tokens |
|--------|------|---------------------|------------|
| 1 | `agent.py` | Production Python agent class, all capabilities implemented | 4096 |
| 2 | `main.py` | Entry point, imports agent class, framework-aware startup | 4096 |
| 3 | `requirements.txt` | Precise dependency list with version pins | 4096 |
| 4 | `README.md` | Documentation with setup + run instructions | 4096 |

4. **Clean each output:**
   - Strip markdown fences (`'''python ... '''`)
   - Remove preamble prose ("Here is the code...")
   - Deduplicate import statements
   - Strip secret keys with regex (`sk-xxx`, `api_key="..."`)
   - Strip trailing commentary

5. **Validate output:**
   - Check for class definition in `agent.py`
   - Check for `__init__` method
   - Detect duplicate imports
   - Detect `self.x` used but not assigned in `__init__`
   - Verify `requirements.txt` is non-empty

6. Save all 4 files to `generated_agent/` directory

**Capability Hints:** The prompt builder includes library-specific implementation hints:

| Capability Keyword | Hint Provided |
|-------------------|---------------|
| `csv` | `csv.DictReader` from stdlib |
| `named entity` | `spacy.load('en_core_web_sm')` |
| `json` | `json.dump(data, f, indent=2)` |
| `web scraping` | `requests` + `BeautifulSoup4` |
| `llm` | Groq SDK pattern |
| `pdf` | `PyPDF2.PdfReader` |
| `email` | `smtplib` + `email.mime` |
| `file monitoring` | `watchdog` |

**Retry:** Each file generation retries up to 3 times on `RuntimeError`.

**Output directory:** `generated_agent/`
```
generated_agent/
├── agent.py           # Main agent class with all capabilities
├── main.py            # Entry point script
├── requirements.txt   # Python dependencies
└── README.md          # Setup and usage documentation
```

---

### Step 4: Verifier Agent (`verifier.py`)

**Purpose:** Score the generated code against the spec using 3 verification layers.

**Process:**
1. Load `generated_agent/agent.py`, `generated_agent/main.py`, and `final_agent.json`
2. Run 3 verification layers sequentially:

#### Layer 1 — AST Syntax Check (Weight: 15%)
- Uses Python's `ast.parse()` to check both files
- **Instant** — no LLM call
- Score: 100 if both pass, 50 if one fails, 0 if both fail
- Catches syntax errors before any further processing

#### Layer 2 — Spec Compliance Check (Weight: 30%)
- **Rule-based AST walk** — no LLM call
- Examines the code structure deterministically:

| Check | What It Verifies |
|-------|-----------------|
| `agent_class_exists` | A class containing the agent name or "agent" exists |
| `framework_imported` | Specified framework is imported |
| `capability_*` | Keywords from each capability appear in the code |
| `language_is_python` | Python files exist (trivially true) |
| `api_*` | External API references found |
| `entrypoint_exists` | `main.py` has `__main__` or a `main()` function |
| `no_placeholders` | No `TODO`, `FIXME`, `pass  #`, `raise NotImplementedError`, `your_api_key` |

- Score = `(checks_passed / total_checks) * 100`

#### Layer 3 — Groq Semantic Review (Weight: 55%)
- **LLM call** to Groq for deep semantic code audit
- System prompt enforces strict JSON-only output
- Returns structured review:

```json
{
  "correctness_percentage": 85,
  "implemented_correctly": ["..."],
  "implemented_partially": ["..."],
  "not_implemented": ["..."],
  "hallucinated_features": ["..."],
  "security_issues": ["..."],
  "issues": ["..."],
  "summary": "one sentence verdict"
}
```

3. **Composite Score:**

```
final_score = (L1 × 15/100) + (L2 × 30/100) + (L3 × 55/100)
```

4. **Correctness Band:**

| Score Range | Band | Meaning |
|-------------|------|---------|
| 85–100 | `READY` | Ship it |
| 75–84 | `ACCEPTABLE` | Deliver with notes |
| 60–74 | `PARTIAL` | Functional but incomplete |
| 0–59 | `REJECT` | Needs regeneration |

**Output file:** `verifier_result.json`

---

## 6. Backend Agent Modules — Deep Dive

### `groq_utils.py` — Shared LLM Client

**Purpose:** Centralized Groq API access with robust JSON extraction.

| Function | Description |
|----------|-------------|
| `require_groq_api_key()` | Reads `GROQ_API_KEY` from env, raises if missing |
| `groq_client()` | Returns configured `Groq()` instance |
| `groq_chat(messages, model, temperature, max_tokens)` | Raw text LLM call |
| `groq_chat_json(system, user, model, ...)` | LLM call + automatic JSON extraction |
| `_extract_first_json_object(text)` | 3-tier JSON extraction: direct parse → regex `{...}` → trailing comma fix |

**JSON extraction strategy:**
1. Try `json.loads(raw)` directly
2. Strip markdown code fences (`'''json ... '''`)
3. Regex extract first `{...}` block
4. Fix common LLM issues (trailing commas before `}` or `]`)

### `code_interface_agent.py`

**Purpose:** Generate a Markdown report (`output.md`) from a folder of generated agent files.

Used optionally when the user wants a documentation export of the generated project.

---

## 7. Server Orchestration (`server.py`)

### Architecture

```
Flask App (server.py)
├── Static Files: ./frontend/ (index.html, style.css, app.js)
├── Auth Endpoints: /api/auth/*
├── Pipeline Endpoints: /api/generate, /api/confirm/<id>
├── Status Endpoints: /api/status/<id>, /api/result/<id>
├── History Endpoint: /api/history
└── Background Threads: pipeline execution
```

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Serve `frontend/index.html` |
| `GET` | `/<path>` | No | Serve static frontend assets |
| `POST` | `/api/auth/signup` | No | Create account (returns token) |
| `POST` | `/api/auth/login` | No | Login (returns token) |
| `GET` | `/api/auth/me` | Yes | Validate token, return user info |
| `POST` | `/api/auth/logout` | Yes | Invalidate token |
| `POST` | `/api/generate` | Yes | Start pipeline (returns `job_id`) |
| `POST` | `/api/confirm/<id>` | Yes | Confirm edited spec, continue pipeline |
| `GET` | `/api/status/<id>` | No | Poll job status and step progress |
| `GET` | `/api/result/<id>` | No | Fetch final artifacts (code files, verifier result) |
| `GET` | `/api/history` | No | Last 50 prompts from `input.csv` |

### Job Lifecycle States

```
running → awaiting_confirmation → running → done
                                          → error
```

| State | Meaning |
|-------|---------|
| `running` | Pipeline actively executing a step |
| `awaiting_confirmation` | Paused after extraction — waiting for user to confirm JSON spec |
| `done` | All steps complete, artifacts available |
| `error` | A step failed (after retries if applicable) |

### Pipeline Step Statuses

Each step in a job has its own status:

| Status | Meaning |
|--------|---------|
| `pending` | Not started yet |
| `running` | Currently executing |
| `done` | Completed successfully |
| `error` | Failed (error message attached) |
| `waiting` | Waiting for a prior gate (confirmation) |
| `skipped` | Not applicable (conversational route) |

### Threading Model

- Pipeline execution runs on a **daemon thread** (`threading.Thread`)
- Job state is stored in an **in-memory dict** (`jobs: dict`)
- Frontend polls `GET /api/status/<id>` every 1.2 seconds
- Subprocess calls use `encoding="utf-8"` + `errors="replace"` for Windows compatibility

### Subprocess Environment

```python
SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
```

This forces all child processes to output UTF-8, preventing `UnicodeDecodeError` on Windows (which defaults to `cp1252`).

---

## 8. Frontend Architecture

### Page Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     AUTH OVERLAY (login/signup)              │
└─────────────────────────────────────────────────────────────┘
                              ↓ (after login)
┌──────────┬──────────────────────────────────────────────────┐
│ SIDEBAR  │                  MAIN CONTENT                    │
│          │  ┌─────────────────┬──────────────────────────┐  │
│ • Brand  │  │  CONVERSATION   │     PIPELINE + ARTIFACTS │  │
│ • History│  │  Panel          │     Panel                │  │
│ • Report │  │                 │                          │  │
│ • Score  │  │  • Chat msgs    │  • Step progress         │  │
│ • User   │  │  • Composer     │  • Tab panel:            │  │
│ • Server │  │    (textarea)   │    - Report              │  │
│          │  │                 │    - agent.py             │  │
│          │  │                 │    - main.py              │  │
│          │  │                 │    - requirements.txt     │  │
│          │  │                 │    - README.md            │  │
│          │  │                 │    - Spec JSON (editable) │  │
│          │  └─────────────────┴──────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────┘
```

### Auth Overlay

- Fullscreen overlay with frosted glass card
- Tabbed interface: **Sign In** / **Create Account**
- Validates form fields before submit
- Displays server errors inline (`.form-error`)
- Auto-login on page refresh if token is valid

### Client-Side State

| Variable | Purpose |
|----------|---------|
| `jobId` | Current pipeline job ID |
| `pollTimer` | `setInterval` ID for status polling |
| `isRunning` | Prevents double-submission |
| `awaitingSpecConfirmation` | True when pipeline paused at confirmation gate |
| `latestResult` | Cached result data for report switching |
| `reportView` | Current report tab: `summary`, `verifier`, `attempts` |

### Token Management

```javascript
localStorage.setItem("agentforge_token", token);     // stored on login
localStorage.setItem("agentforge_user", JSON.stringify(user));

// Sent with every protected API call:
headers: { Authorization: `Bearer ${token}` }
```

### Design System

| Token | Value | Used For |
|-------|-------|----------|
| `--bg` | `#09090b` | Page background |
| `--panel` | `#111318` | Card/panel backgrounds |
| `--accent` | `#60a5fa` | Primary blue accent |
| `--accent2` | `#a78bfa` | Secondary purple accent |
| `--good` | `#34d399` | Success states |
| `--bad` | `#f87171` | Error states |
| `--radius` | `12px` | Standard border radius |

### Animations

| Animation | Element | Effect |
|-----------|---------|--------|
| `msgIn` | Chat messages | Slide up + fade in (0.3s) |
| `stepPulse` | Running pipeline step | Pulsing box-shadow (2s loop) |
| `toastIn` | Toast notifications | Slide up + scale up (0.3s) |

---

## 9. Data Flow Diagram

```
USER INPUT
    │
    ▼
┌────────────────┐
│  Frontend      │──── POST /api/generate ────▶ server.py
│  (app.js)      │                             │
└────────────────┘                             ▼
                                          save_input_to_csv()
                                               │
                                               ▼
                                    ┌───────────────────┐
                                    │ perspective_agent  │
                                    │    .py             │
                                    └───────┬───────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                    build_agent_output.json    conversational_output.json
                    (agent_building route)     (conversational route)
                              │                           │
                              ▼                           ▼
                    ┌──────────────────┐          Response sent to
                    │ inputextractor.py│          frontend chat
                    └────────┬─────────┘          (pipeline stops)
                             │
                             ▼
                      final_agent.json
                             │
                             ▼
                   ┌──────────────────────┐
                   │ CONFIRMATION GATE    │
                   │ User reviews/edits   │
                   │ the JSON spec in UI  │
                   └────────┬─────────────┘
                            │
                   POST /api/confirm/<id>
                            │
                            ▼
                   ┌──────────────────┐
                   │  agentbuild.py   │
                   └────────┬─────────┘
                            │
                            ▼
                   generated_agent/
                   ├── agent.py
                   ├── main.py
                   ├── requirements.txt
                   └── README.md
                            │
                            ▼
                   ┌──────────────────┐
                   │   verifier.py    │
                   └────────┬─────────┘
                            │
                            ▼
                   verifier_result.json
                   {
                     correctness_score: 87.5,
                     correctness_band: "READY",
                     layer_scores: {...}
                   }
                            │
                            ▼
                   Frontend displays results
                   (artifacts, score, report)
```

---

## 10. Artifact Files & Intermediate Outputs

| File | Created By | Used By | Lifecycle |
|------|-----------|---------|-----------|
| `input.csv` | `server.py` / `main.py` | `perspective_agent.py`, `inputextractor.py` | Append-only, persists |
| `build_agent_output.json` | `perspective_agent.py` | `server.py` (classification data) | Cleaned before each run |
| `conversational_output.json` | `perspective_agent.py` | `server.py` (conversational response) | Cleaned before each run |
| `final_agent.json` | `inputextractor.py` → user edits | `agentbuild.py`, `verifier.py` | Cleaned before each run |
| `generated_agent/*.py` | `agentbuild.py` | `verifier.py`, user download | Overwritten each run |
| `verifier_result.json` | `verifier.py` | `server.py` (score/band/decision) | Cleaned before each run |
| `agentforge.db` | `auth.py` (auto-created) | `auth.py`, `server.py` | Persistent |

### Stale Output Cleanup

Before each pipeline run, `_clean_stale_outputs()` deletes:
- `build_agent_output.json`
- `conversational_output.json`
- `final_agent.json`
- `verifier_result.json`

This prevents leftover data from a previous run from contaminating the current one.

---

## 11. Retry & Regeneration Logic

### Code Generation Retries (in `server.py`)

The pipeline supports up to **3 total attempts** (1 initial + 2 retries):

```
Attempt 1: Generate Code → Verify → Score
    If REJECT → retry
    If PARTIAL (first time) → retry once more
    If READY/ACCEPTABLE → deliver

Attempt 2: Regenerate Code → Re-verify → Re-score
    Same logic...

Attempt 3 (max): Whatever the result, deliver it
```

| Band | Action |
|------|--------|
| `READY` (≥85) | Deliver immediately |
| `ACCEPTABLE` (75–84) | Deliver with verification notes |
| `PARTIAL` (60–74) | Retry once, then deliver |
| `REJECT` (<60) | Retry up to 2 times, then deliver with rejection note |

### LLM Call Retries (in `agentbuild.py`)

Each individual file generation (`agent.py`, `main.py`, etc.) retries up to 3 times on `RuntimeError` before failing the entire step.

---

## 12. Scoring & Verification System

### Weight Distribution

| Layer | Weight | Type | Speed |
|-------|--------|------|-------|
| Layer 1: AST Syntax | 15% | Deterministic | Instant |
| Layer 2: Spec Compliance | 30% | Rule-based | Instant |
| Layer 3: LLM Semantic | 55% | LLM call | ~3–8 seconds |

### Composite Score Formula

```
score = (L1_score × 0.15) + (L2_score × 0.30) + (L3_score × 0.55)
```

### Example Scoring

| Scenario | L1 | L2 | L3 | Final | Band |
|----------|----|----|----|----|------|
| Perfect code | 100 | 100 | 95 | 97.25 | READY |
| Minor gaps | 100 | 85 | 78 | 83.4 | ACCEPTABLE |
| Missing features | 100 | 60 | 55 | 63.25 | PARTIAL |
| Syntax error | 50 | 0 | 40 | 29.5 | REJECT |

---

## 13. CLI Entry Point (`main.py`)

The CLI orchestrator provides a **colored terminal interface** for running the same pipeline without a browser:

```bash
python main.py
python main.py --input "Build me a web scraping agent"
python main.py --input-file prompt.txt
python main.py --skip-on-failure
```

### CLI Steps

| Step | Script | Description |
|------|--------|-------------|
| 0 | — | Save user input to `input.csv` |
| 1 | `perspective_agent.py` | Classify input |
| 2 | `inputextractor.py` | Extract spec + interactive confirmation |
| 3 | `agentbuild.py` | Generate code |
| 4 | `verifier.py` | Verify and score |

The CLI version includes:
- Colored output (ANSI codes: green ✓, red ✗, yellow ⚠, cyan →)
- Step headers with timing
- Interactive spec confirmation (`yes` / `edit` / `show-language`)
- Final summary with score and band

---

## 14. Environment & Configuration

### `.env` File

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxx
AUTH_SECRET_KEY=your_optional_secret_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GROQ_API_KEY` | **Yes** | — | Groq Cloud API authentication |
| `AUTH_SECRET_KEY` | No | Random (regenerated on restart) | Signs session tokens |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | LLM model for all calls |

> **Warning:** If `AUTH_SECRET_KEY` is not set in `.env`, a new random key is generated each time `auth.py` is imported. This means **all sessions are invalidated on server restart**. Set it explicitly for persistence.

### Running the Server

```bash
# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Start
python server.py
```

Output:
```
============================================================
  >> AgentForge Server
============================================================
  Frontend : D:\responsible AI newww\frontend
  Backend  : D:\responsible AI newww
  Database : D:\responsible AI newww\agentforge.db
  URL      : http://localhost:5000
============================================================
```

---

## 15. Security Considerations

### Implemented

| Feature | Implementation |
|---------|---------------|
| Password hashing | PBKDF2-HMAC-SHA256, 100k iterations, unique salt per user |
| Token signing | HMAC-SHA256 with server secret |
| Timing-safe comparison | `hmac.compare_digest()` for passwords and tokens |
| Token expiry | 72-hour default |
| Input validation | 3–5000 char limit, basic prompt injection sanitization |
| Secret stripping | Regex removes `sk-xxx` and `api_key="..."` from generated code |
| UTF-8 enforcement | All subprocess calls use `encoding="utf-8"` |
| CORS | Enabled via `flask-cors` |
| SQL injection prevention | Parameterized queries only (`?` placeholders) |

### Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| In-memory job state | Lost on server restart | Future: move to SQLite |
| No rate limiting | API abuse possible | Future: add per-user limits |
| No email verification | Fake emails accepted | Future: email confirmation flow |
| Session not revoked on password change | Old tokens still valid | Future: invalidate all sessions on password change |
| `AUTH_SECRET_KEY` random on restart | All sessions invalidated | Set explicitly in `.env` |

---

> **Last updated:** April 26, 2026
> **Author:** AgentForge Development Team
