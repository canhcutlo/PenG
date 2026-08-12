"""SQLite store for chat sessions and messages."""
import json
import sqlite3
from datetime import datetime, timezone
from app.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.sqlite_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_chat_tables():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            document_id TEXT NOT NULL REFERENCES documents(doc_id),
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL REFERENCES chat_sessions(session_id),
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            citations_json TEXT,
            related_nodes_json TEXT,
            warnings_json TEXT,
            model_id TEXT,
            prompt_version TEXT,
            token_metadata_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_doc ON chat_sessions(user_id, document_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session ON chat_messages(user_id, session_id);
        """
    )
    conn.commit()
    conn.close()


def insert_session(session_id: str, user_id: str, document_id: str, title: str | None) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        INSERT INTO chat_sessions (session_id, user_id, document_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, user_id, document_id, title, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_session(session_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE session_id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def list_sessions(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT s.*, d.original_name AS doc_title
        FROM chat_sessions s
        LEFT JOIN documents d ON s.document_id = d.doc_id
        WHERE s.user_id = ?
        ORDER BY s.updated_at DESC, s.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_session_updated_at(session_id: str):
    conn = get_connection()
    now = _now()
    conn.execute(
        "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
        (now, session_id),
    )
    conn.commit()
    conn.close()


def insert_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    related_nodes: list[dict] | None = None,
    warnings: list[str] | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    token_metadata: dict | None = None,
) -> dict:
    message_id = _generate_message_id(session_id, user_id, role, content)
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        INSERT INTO chat_messages
        (message_id, session_id, user_id, role, content, citations_json, related_nodes_json,
         warnings_json, model_id, prompt_version, token_metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id, session_id, user_id, role, content,
            json.dumps(citations, ensure_ascii=False) if citations else None,
            json.dumps(related_nodes, ensure_ascii=False) if related_nodes else None,
            json.dumps(warnings, ensure_ascii=False) if warnings else None,
            model_id, prompt_version,
            json.dumps(token_metadata, ensure_ascii=False) if token_metadata else None,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM chat_messages WHERE message_id = ?", (message_id,)).fetchone()
    conn.close()
    update_session_updated_at(session_id)
    return _row_to_dict(row)


def get_messages_for_session(session_id: str, limit: int = 100, order: str = "asc") -> list[dict]:
    order_sql = "DESC" if order.lower() == "desc" else "ASC"
    conn = get_connection()
    rows = conn.execute(
        f"""
        SELECT * FROM chat_messages
        WHERE session_id = ?
        ORDER BY id {order_sql}
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def _generate_message_id(session_id: str, user_id: str, role: str, content: str) -> str:
    import hashlib
    base = f"{session_id}:{user_id}:{role}:{content}:{_now()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("citations_json", "related_nodes_json", "warnings_json", "token_metadata_json"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except json.JSONDecodeError:
                d[key] = None
    return d
