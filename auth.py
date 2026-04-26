"""
auth.py — SQLite-backed Authentication Module
================================================
Provides user signup, login, and HMAC-signed session management.
Database: agentforge.db (SQLite, auto-created)

Security (G5):
  - PBKDF2-HMAC-SHA256 password hashing (100k iterations)
  - HMAC-SHA256 token signing with constant-time comparison
  - Token rotation on login (old sessions invalidated)
  - Session inactivity timeout (24h)
  - Stale session cleanup
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# JWT-like token handling without heavy dependencies
# Uses HMAC-SHA256 for signing

DB_PATH = Path(__file__).parent / "agentforge.db"
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRY_HOURS = 72          # 3 days — hard token expiry
INACTIVITY_TIMEOUT_HOURS = 24   # G5B — sessions unused for 24h are expired
MAX_SESSIONS_PER_USER = 3       # G5A — max concurrent sessions per user


# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Get a new database connection with row_factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password    TEXT    NOT NULL,
            salt        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login  TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token       TEXT    NOT NULL UNIQUE,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL,
            last_used   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """)
    conn.commit()

    # Migrate: add last_used column if it doesn't exist (for upgrades)
    try:
        conn.execute("SELECT last_used FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        # SQLite cannot ALTER TABLE with non-constant defaults; use empty string
        conn.execute("ALTER TABLE sessions ADD COLUMN last_used TEXT NOT NULL DEFAULT ''")
        # Backfill existing rows with current time
        conn.execute("UPDATE sessions SET last_used = datetime('now') WHERE last_used = ''")
        conn.commit()

    conn.close()


# ─────────────────────────────────────────────
#  PASSWORD HASHING (PBKDF2 — no extra deps)
# ─────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256, 100k iterations."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return dk.hex()


def _verify_password(password: str, salt: str, hashed: str) -> bool:
    """Constant-time comparison of password hash."""
    return hmac.compare_digest(_hash_password(password, salt), hashed)


# ─────────────────────────────────────────────
#  TOKEN MANAGEMENT (HMAC-signed JSON tokens)
# ─────────────────────────────────────────────

def _create_token(user_id: int, username: str) -> str:
    """Create a signed token containing user info + expiry."""
    import base64
    expires = int(time.time()) + TOKEN_EXPIRY_HOURS * 3600
    payload = json.dumps({
        "uid": user_id,
        "usr": username,
        "exp": expires,
    }, separators=(",", ":"))
    b64payload = base64.urlsafe_b64encode(payload.encode()).decode()
    signature = hmac.new(
        SECRET_KEY.encode(),
        b64payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{b64payload}.{signature}"


def _verify_token(token: str) -> dict | None:
    """Verify token signature and expiry. Returns payload or None."""
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64payload, signature = parts
        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            b64payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(b64payload))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ─────────────────────────────────────────────
#  SESSION MANAGEMENT (G5)
# ─────────────────────────────────────────────

def _invalidate_user_sessions(conn: sqlite3.Connection, user_id: int) -> int:
    """
    G5A — Token rotation: remove ALL existing sessions for a user
    before creating a new one. Limits session replay attacks.

    Returns count of sessions removed.
    """
    cursor = conn.execute(
        "DELETE FROM sessions WHERE user_id = ?",
        (user_id,),
    )
    return cursor.rowcount


def _enforce_session_limit(conn: sqlite3.Connection, user_id: int) -> None:
    """
    G5A — Keep only the most recent MAX_SESSIONS_PER_USER sessions.
    Deletes oldest sessions if the limit is exceeded.
    """
    sessions = conn.execute(
        "SELECT id FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    if len(sessions) > MAX_SESSIONS_PER_USER:
        excess = [s["id"] for s in sessions[MAX_SESSIONS_PER_USER:]]
        placeholders = ",".join("?" * len(excess))
        conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            excess,
        )


def _touch_session(conn: sqlite3.Connection, token: str) -> None:
    """G5B — Update last_used timestamp on every auth check."""
    conn.execute(
        "UPDATE sessions SET last_used = datetime('now') WHERE token = ?",
        (token,),
    )
    conn.commit()


def cleanup_expired_sessions() -> int:
    """
    Remove sessions that are expired by time or inactive for too long.
    Called periodically by a daemon thread.

    Returns count of sessions removed.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE "
            "expires_at < datetime('now') "
            "OR last_used < datetime('now', ?)",
            (f"-{INACTIVITY_TIMEOUT_HOURS} hours",),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────

def signup(username: str, email: str, password: str) -> dict:
    """
    Register a new user.
    Returns: {"success": True, "user": {...}} or {"success": False, "error": "..."}
    """
    username = username.strip()
    email = email.strip().lower()
    password = password.strip()

    if not username or len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters"}
    if len(username) > 30:
        return {"success": False, "error": "Username must be 30 characters or less"}
    if not email or "@" not in email:
        return {"success": False, "error": "Invalid email address"}
    if not password or len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    salt = secrets.token_hex(16)
    hashed = _hash_password(password, salt)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password, salt) VALUES (?, ?, ?, ?)",
            (username, email, hashed, salt),
        )
        conn.commit()
        user = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        return {
            "success": True,
            "user": dict(user),
        }
    except sqlite3.IntegrityError as e:
        err_msg = str(e).lower()
        if "username" in err_msg:
            return {"success": False, "error": "Username already taken"}
        if "email" in err_msg:
            return {"success": False, "error": "Email already registered"}
        return {"success": False, "error": "Account already exists"}
    finally:
        conn.close()


def login(email: str, password: str) -> dict:
    """
    Authenticate user and return a session token.
    G5A: Invalidates ALL previous sessions (token rotation).
    Returns: {"success": True, "token": "...", "user": {...}} or error.
    """
    email = email.strip().lower()
    password = password.strip()

    if not email or not password:
        return {"success": False, "error": "Email and password are required"}

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, email, password, salt, created_at FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            return {"success": False, "error": "Invalid email or password"}

        if not _verify_password(password, user["salt"], user["password"]):
            return {"success": False, "error": "Invalid email or password"}

        # G5A — Token rotation: invalidate ALL existing sessions for this user
        removed = _invalidate_user_sessions(conn, user["id"])

        # Create fresh token
        token = _create_token(user["id"], user["username"])

        # Store new session in DB
        expires_at = datetime.utcfromtimestamp(
            time.time() + TOKEN_EXPIRY_HOURS * 3600
        ).isoformat()
        conn.execute(
            "INSERT INTO sessions (user_id, token, expires_at, last_used) "
            "VALUES (?, ?, ?, datetime('now'))",
            (user["id"], token, expires_at),
        )
        conn.execute(
            "UPDATE users SET last_login = datetime('now') WHERE id = ?",
            (user["id"],),
        )
        conn.commit()

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
            },
        }
    finally:
        conn.close()


def get_user_from_token(token: str) -> dict | None:
    """
    Validate token and return user info.
    G5B: Also checks session exists in DB and wasn't inactive too long.
         Updates last_used timestamp on successful validation.
    Returns user dict or None if invalid/expired.
    """
    payload = _verify_token(token)
    if not payload:
        return None

    conn = get_db()
    try:
        # G5B — Check session exists in DB and is not expired / inactive
        session = conn.execute(
            "SELECT id, user_id FROM sessions WHERE token = ? "
            "AND expires_at > datetime('now') "
            "AND last_used > datetime('now', ?)",
            (token, f"-{INACTIVITY_TIMEOUT_HOURS} hours"),
        ).fetchone()

        if not session:
            # Session doesn't exist, is expired, or is inactive — reject
            return None

        # Touch session to reset inactivity timer
        _touch_session(conn, token)

        user = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (payload["uid"],)
        ).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()


def logout(token: str) -> bool:
    """Remove session from database."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return True
    finally:
        conn.close()


def logout_all(user_id: int) -> int:
    """Remove ALL sessions for a user (e.g., password change)."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# Initialize database on import
init_db()
