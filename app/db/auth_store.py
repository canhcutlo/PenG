"""SQLite store for users, sessions, and auth-related migrations."""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from app.config import settings


SYSTEM_USER_ID = "000000000000"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.sqlite_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def init_auth_tables():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
        """
    )
    conn.commit()
    conn.close()


def migrate_ownership_columns():
    """Add user_id columns to existing MVP tables. Idempotent."""
    conn = get_connection()
    tables = {
        "documents": "doc_id",
        "activities": "id",
        "quizzes": "quiz_id",
        "quiz_results": "id",
    }
    for table, pk in tables.items():
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
        except sqlite3.OperationalError:
            pass

    try:
        conn.execute("ALTER TABLE processing_jobs ADD COLUMN user_id TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def create_indexes():
    conn = get_connection()
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
        CREATE INDEX IF NOT EXISTS idx_documents_user_checksum ON documents(user_id, checksum_sha256);
        CREATE INDEX IF NOT EXISTS idx_activities_user_id ON activities(user_id);
        CREATE INDEX IF NOT EXISTS idx_activities_user_created ON activities(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_quizzes_user_id ON quizzes(user_id);
        CREATE INDEX IF NOT EXISTS idx_quiz_results_quiz_id ON quiz_results(quiz_id);
        """
    )
    conn.commit()
    conn.close()


def ensure_system_user() -> str:
    """Create the system user and backfill existing rows. Returns system user_id."""
    init_auth_tables()
    migrate_ownership_columns()
    create_indexes()

    conn = get_connection()
    now = _now()

    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (SYSTEM_USER_ID,),
    ).fetchone()

    if not row:
        conn.execute(
            "INSERT INTO users (user_id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (SYSTEM_USER_ID, settings.auth_system_user_username, "", now),
        )

    conn.execute(
        "UPDATE documents SET user_id = COALESCE(user_id, ?) WHERE user_id IS NULL",
        (SYSTEM_USER_ID,),
    )
    conn.execute(
        "UPDATE activities SET user_id = COALESCE(user_id, ?) WHERE user_id IS NULL",
        (SYSTEM_USER_ID,),
    )
    conn.execute(
        "UPDATE quizzes SET user_id = COALESCE(user_id, ?) WHERE user_id IS NULL",
        (SYSTEM_USER_ID,),
    )
    conn.execute(
        "UPDATE quiz_results SET user_id = COALESCE(user_id, ?) WHERE user_id IS NULL",
        (SYSTEM_USER_ID,),
    )
    conn.execute(
        "UPDATE processing_jobs SET user_id = COALESCE(user_id, ?) WHERE user_id IS NULL",
        (SYSTEM_USER_ID,),
    )

    conn.commit()
    conn.close()
    return SYSTEM_USER_ID


def create_user(user_id: str, username: str, password_hash: str) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        "INSERT INTO users (user_id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, password_hash, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT user_id, username, created_at FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row)


def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id, username, created_at FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_session(user_id: str) -> str:
    """Create a new opaque session token; return the raw token."""
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.auth_cookie_max_age_seconds)

    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (session_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, now.isoformat(), expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_session_by_hash(token_hash: str) -> dict | None:
    conn = get_connection()
    now = _now()
    row = conn.execute(
        "SELECT * FROM sessions WHERE session_hash = ? AND expires_at > ?",
        (token_hash, now),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(token_hash: str):
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE session_hash = ?", (token_hash,))
    conn.commit()
    conn.close()


def delete_user_sessions(user_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
