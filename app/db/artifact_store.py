"""SQLite store for document artifacts (summary, mindmap)."""
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


def init_artifact_tables():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_artifacts (
            artifact_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('summary','mindmap')),
            version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','processing','completed','failed')),
            content TEXT,
            input_snapshot TEXT,
            language TEXT,
            model_id TEXT,
            llm_config TEXT,
            generation_params TEXT,
            prompt_version TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_artifacts_doc_id ON document_artifacts(doc_id);
        CREATE INDEX IF NOT EXISTS idx_artifacts_user_doc_type
            ON document_artifacts(user_id, doc_id, type);
        CREATE INDEX IF NOT EXISTS idx_artifacts_doc_type_version
            ON document_artifacts(doc_id, type, version DESC);
        """
    )
    conn.commit()
    conn.close()


def insert_artifact(artifact_id: str, doc_id: str, user_id: str, artifact_type: str, version: int,
                    status: str = "queued", content: str | None = None,
                    input_snapshot: dict | None = None, language: str | None = None,
                    model_id: str | None = None, llm_config: dict | None = None,
                    generation_params: dict | None = None, prompt_version: str | None = None,
                    attempts: int = 0, error_message: str | None = None) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        INSERT INTO document_artifacts
        (artifact_id, doc_id, user_id, type, version, status, content, input_snapshot,
         language, model_id, llm_config, generation_params, prompt_version, attempts,
         error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id, doc_id, user_id, artifact_type, version, status, content,
            json.dumps(input_snapshot, ensure_ascii=False) if input_snapshot else None,
            language, model_id,
            json.dumps(llm_config, ensure_ascii=False) if llm_config else None,
            json.dumps(generation_params, ensure_ascii=False) if generation_params else None,
            prompt_version, attempts, error_message, now,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM document_artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row)


def update_artifact_status(artifact_id: str, status: str, content: str | None = None,
                           error_message: str | None = None, attempts: int | None = None):
    conn = get_connection()
    updates = ["status = ?"]
    params: list = [status]
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if attempts is not None:
        updates.append("attempts = ?")
        params.append(attempts)
    params.append(artifact_id)
    sql = f"UPDATE document_artifacts SET {', '.join(updates)} WHERE artifact_id = ?"
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def get_latest_artifact(doc_id: str, artifact_type: str, status: str | None = None) -> dict | None:
    conn = get_connection()
    if status:
        row = conn.execute(
            """
            SELECT * FROM document_artifacts
            WHERE doc_id = ? AND type = ? AND status = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (doc_id, artifact_type, status),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM document_artifacts
            WHERE doc_id = ? AND type = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (doc_id, artifact_type),
        ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_artifacts_by_doc(doc_id: str, artifact_type: str | None = None, limit: int = 20) -> list[dict]:
    conn = get_connection()
    if artifact_type:
        rows = conn.execute(
            """
            SELECT * FROM document_artifacts
            WHERE doc_id = ? AND type = ?
            ORDER BY version DESC, created_at DESC
            LIMIT ?
            """,
            (doc_id, artifact_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM document_artifacts
            WHERE doc_id = ?
            ORDER BY version DESC, created_at DESC
            LIMIT ?
            """,
            (doc_id, limit),
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_artifact(artifact_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM document_artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def count_artifacts(doc_id: str, artifact_type: str) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM document_artifacts WHERE doc_id = ? AND type = ?",
        (doc_id, artifact_type),
    ).fetchone()
    conn.close()
    return row["cnt"]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("input_snapshot", "llm_config", "generation_params"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except json.JSONDecodeError:
                d[key] = None
    return d
