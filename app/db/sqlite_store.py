"""SQLite store for documents, jobs, activities, quizzes, and quiz results."""
import sqlite3
import json
from datetime import datetime, timezone
from app.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.sqlite_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_sqlite():
    from app.db.auth_store import ensure_system_user
    from app.db.artifact_store import init_artifact_tables
    from app.db.chunk_store import init_chunk_tables
    from app.db.knowledge_store import init_knowledge_tables
    from app.db.chat_store import init_chat_tables

    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('audio','image','pdf','video')),
            file_size INTEGER NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','processing','completed','failed')),
            user_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS processing_jobs (
            job_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            job_type TEXT NOT NULL CHECK(job_type IN ('extract','index')),
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','processing','completed','failed')),
            progress INTEGER NOT NULL DEFAULT 0,
            stage TEXT,
            stage_label TEXT,
            error_message TEXT,
            user_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            action TEXT NOT NULL,
            metadata_json TEXT,
            user_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            user_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            user_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    for col in ("stage", "stage_label"):
        try:
            conn.execute(f"ALTER TABLE processing_jobs ADD COLUMN {col} TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    conn.close()

    ensure_system_user()
    init_artifact_tables()
    init_chunk_tables()
    init_knowledge_tables()
    init_chat_tables()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_document(
    doc_id: str,
    filename: str,
    original_name: str,
    category: str,
    file_size: int,
    checksum_sha256: str,
    user_id: str,
) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """INSERT INTO documents (doc_id, filename, original_name, category,
           file_size, checksum_sha256, status, user_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
        (doc_id, filename, original_name, category, file_size, checksum_sha256, user_id, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row)


def get_document(doc_id: str, user_id: str | None = None) -> dict | None:
    conn = get_connection()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_document_by_checksum(checksum: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM documents WHERE checksum_sha256 = ? AND user_id = ?",
        (checksum, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_document_status(doc_id: str, status: str):
    conn = get_connection()
    now = _now()
    conn.execute(
        "UPDATE documents SET status = ?, updated_at = ? WHERE doc_id = ?",
        (status, now, doc_id),
    )
    conn.commit()
    conn.close()


def get_documents_for_user(user_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_job(job_id: str, doc_id: str, job_type: str, user_id: str) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """INSERT INTO processing_jobs (job_id, doc_id, job_type, status, progress, stage, stage_label, user_id, created_at)
           VALUES (?, ?, ?, 'queued', 0, ?, ?, ?, ?)""",
        (job_id, doc_id, job_type, "queued", "Đang chờ xử lý", user_id, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_job(job_id: str, user_id: str | None = None) -> dict | None:
    conn = get_connection()
    if user_id is not None:
        row = conn.execute(
            """
            SELECT j.* FROM processing_jobs j
            JOIN documents d ON j.doc_id = d.doc_id
            WHERE j.job_id = ? AND d.user_id = ?
            """,
            (job_id, user_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_job(
    job_id: str,
    status: str,
    progress: int = 0,
    error_message: str | None = None,
    stage: str | None = None,
    stage_label: str | None = None,
):
    conn = get_connection()
    now = _now()
    conn.execute(
        """UPDATE processing_jobs
           SET status = ?, progress = ?, error_message = ?,
               stage = COALESCE(?, stage),
               stage_label = COALESCE(?, stage_label),
               updated_at = ?
           WHERE job_id = ?""",
        (status, progress, error_message, stage, stage_label, now, job_id),
    )
    conn.commit()
    conn.close()


def log_activity(doc_id: str, action: str, user_id: str, metadata: dict | None = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO activities (doc_id, action, metadata_json, user_id) VALUES (?, ?, ?, ?)",
        (doc_id, action, json.dumps(metadata, ensure_ascii=False) if metadata else None, user_id),
    )
    conn.commit()
    conn.close()


def get_activities(user_id: str, limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM activities WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_quiz(quiz_id: str, doc_id: str, questions: list[dict], user_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO quizzes (quiz_id, doc_id, questions_json, user_id) VALUES (?, ?, ?, ?)",
        (quiz_id, doc_id, json.dumps(questions, ensure_ascii=False), user_id),
    )
    conn.commit()
    conn.close()


def get_quiz(quiz_id: str, user_id: str | None = None) -> dict | None:
    conn = get_connection()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM quizzes WHERE quiz_id = ? AND user_id = ?",
            (quiz_id, user_id),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["questions"] = json.loads(d["questions_json"])
        return d
    return None


def insert_quiz_result(quiz_id: str, answers_json: str, score: int, user_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO quiz_results (quiz_id, answers_json, score, user_id) VALUES (?, ?, ?, ?)",
        (quiz_id, answers_json, score, user_id),
    )
    conn.commit()
    conn.close()


def get_quiz_results(user_id: str, limit: int = 100) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM quiz_results WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
