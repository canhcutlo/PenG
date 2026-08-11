"""SQLite store for indexed document chunks used by chat retrieval."""
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


def init_chunk_tables():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            page INTEGER,
            scene INTEGER,
            timestamp REAL,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON document_chunks(user_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_user_doc ON document_chunks(user_id, doc_id);
        """
    )
    conn.commit()
    conn.close()


def insert_chunks(chunks: list[dict], user_id: str):
    if not chunks:
        return
    conn = get_connection()
    now = _now()
    rows = []
    for chunk in chunks:
        rows.append(
            (
                chunk["chunk_id"],
                chunk["doc_id"],
                user_id,
                chunk["text"],
                chunk.get("page"),
                chunk.get("scene"),
                chunk.get("timestamp"),
                json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
                now,
            )
        )
    conn.executemany(
        """
        INSERT INTO document_chunks
        (chunk_id, doc_id, user_id, text, page, scene, timestamp, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def get_chunks_for_doc(doc_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute(
            "SELECT * FROM document_chunks WHERE doc_id = ? AND user_id = ? ORDER BY chunk_id",
            (doc_id, user_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM document_chunks WHERE doc_id = ? ORDER BY chunk_id", (doc_id,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_chunks_for_docs(doc_ids: list[str], user_id: str) -> list[dict]:
    if not doc_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" * len(doc_ids))
    rows = conn.execute(
        f"""
        SELECT * FROM document_chunks
        WHERE doc_id IN ({placeholders}) AND user_id = ?
        ORDER BY chunk_id
        """,
        (*doc_ids, user_id),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_chunks_for_user(user_id: str, exclude_doc_id: str | None = None, limit: int = 2000) -> list[dict]:
    conn = get_connection()
    if exclude_doc_id:
        rows = conn.execute(
            """
            SELECT * FROM document_chunks
            WHERE user_id = ? AND doc_id != ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, exclude_doc_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM document_chunks
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_chunks_for_doc(doc_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    meta = d.get("metadata_json")
    if isinstance(meta, str):
        try:
            d["metadata"] = json.loads(meta)
        except json.JSONDecodeError:
            d["metadata"] = {}
    return d
