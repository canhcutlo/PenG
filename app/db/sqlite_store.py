"""SQLite store for documents, jobs, activities, quizzes, and quiz results."""
import sqlite3
import json
from datetime import datetime, timezone
from app.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.sqlite_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_sqlite():
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
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            action TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()




def insert_document(
    doc_id: str,
    filename: str,
    original_name: str,
    category: str,
    file_size: int,
    checksum_sha256: str,
) -> dict:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO documents (doc_id, filename, original_name, category,
           file_size, checksum_sha256, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)""",
        (doc_id, filename, original_name, category, file_size, checksum_sha256, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row)


def get_document(doc_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def find_document_by_checksum(checksum: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM documents WHERE checksum_sha256 = ?",
        (checksum,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_document_status(doc_id: str, status: str):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE documents SET status = ?, updated_at = ? WHERE doc_id = ?",
        (status, now, doc_id),
    )
    conn.commit()
    conn.close()




def insert_job(job_id: str, doc_id: str, job_type: str) -> dict:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO processing_jobs (job_id, doc_id, job_type, status, created_at)
           VALUES (?, ?, ?, 'queued', ?)""",
        (job_id, doc_id, job_type, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM processing_jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_job(job_id: str, status: str, progress: int = 0, error_message: str | None = None):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE processing_jobs
           SET status = ?, progress = ?, error_message = ?, updated_at = ?
           WHERE job_id = ?""",
        (status, progress, error_message, now, job_id),
    )
    conn.commit()
    conn.close()




def log_activity(doc_id: str, action: str, metadata: dict | None = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO activities (doc_id, action, metadata_json) VALUES (?, ?, ?)",
        (doc_id, action, json.dumps(metadata) if metadata else None),
    )
    conn.commit()
    conn.close()


def get_activities(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM activities ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]




def insert_quiz(quiz_id: str, doc_id: str, questions: list[dict]):
    conn = get_connection()
    conn.execute(
        "INSERT INTO quizzes (quiz_id, doc_id, questions_json) VALUES (?, ?, ?)",
        (quiz_id, doc_id, json.dumps(questions)),
    )
    conn.commit()
    conn.close()


def get_quiz(quiz_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["questions"] = json.loads(d["questions_json"])
        return d
    return None


def insert_quiz_result(quiz_id: str, answers_json: str, score: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO quiz_results (quiz_id, answers_json, score) VALUES (?, ?, ?)",
        (quiz_id, answers_json, score),
    )
    conn.commit()
    conn.close()
