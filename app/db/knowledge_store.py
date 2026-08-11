"""SQLite store for knowledge nodes and edges."""
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


def init_knowledge_tables():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            node_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            document_id TEXT NOT NULL REFERENCES documents(doc_id),
            node_type TEXT NOT NULL DEFAULT 'document',
            title TEXT,
            summary TEXT,
            mindmap_markdown TEXT,
            language TEXT,
            labels_json TEXT,
            internal_consistency REAL NOT NULL,
            evidence_coverage REAL NOT NULL,
            extraction_quality REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('accepted','review_required','rejected')),
            version INTEGER NOT NULL DEFAULT 1,
            input_snapshot TEXT,
            model_id TEXT,
            prompt_version TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_edges (
            edge_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id),
            target_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id),
            source_document_id TEXT NOT NULL,
            target_document_id TEXT NOT NULL,
            relation_type TEXT NOT NULL CHECK(relation_type IN ('related_to','supports','contradicts')),
            similarity_score REAL,
            evidence_json TEXT,
            status TEXT NOT NULL DEFAULT 'accepted' CHECK(status IN ('accepted','review_required','rejected')),
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_knodes_user_id ON knowledge_nodes(user_id);
        CREATE INDEX IF NOT EXISTS idx_knodes_document_id ON knowledge_nodes(document_id);
        CREATE INDEX IF NOT EXISTS idx_knodes_user_doc ON knowledge_nodes(user_id, document_id);
        CREATE INDEX IF NOT EXISTS idx_kedges_user_id ON knowledge_edges(user_id);
        CREATE INDEX IF NOT EXISTS idx_kedges_source_doc ON knowledge_edges(source_document_id);
        CREATE INDEX IF NOT EXISTS idx_kedges_target_doc ON knowledge_edges(target_document_id);
        CREATE INDEX IF NOT EXISTS idx_kedges_user_source ON knowledge_edges(user_id, source_document_id);
        """
    )
    conn.commit()
    conn.close()


def insert_node(
    node_id: str,
    user_id: str,
    document_id: str,
    title: str | None,
    summary: str | None,
    mindmap_markdown: str | None,
    language: str | None,
    labels: list[str],
    internal_consistency: float,
    evidence_coverage: float,
    extraction_quality: float,
    status: str,
    version: int,
    input_snapshot: dict | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        INSERT INTO knowledge_nodes
        (node_id, user_id, document_id, node_type, title, summary, mindmap_markdown,
         language, labels_json, internal_consistency, evidence_coverage, extraction_quality,
         status, version, input_snapshot, model_id, prompt_version, created_at)
        VALUES (?, ?, ?, 'document', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id, user_id, document_id, title, summary, mindmap_markdown,
            language, json.dumps(labels, ensure_ascii=False),
            internal_consistency, evidence_coverage, extraction_quality, status,
            version,
            json.dumps(input_snapshot, ensure_ascii=False) if input_snapshot else None,
            model_id, prompt_version, now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM knowledge_nodes WHERE node_id = ?", (node_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_latest_node(document_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT * FROM knowledge_nodes
        WHERE document_id = ? AND user_id = ?
        ORDER BY version DESC, created_at DESC
        LIMIT 1
        """,
        (document_id, user_id),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_node(node_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM knowledge_nodes WHERE node_id = ? AND user_id = ?",
        (node_id, user_id),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_nodes_for_user(user_id: str, limit: int = 1000) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM knowledge_nodes
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def delete_edges_for_source_document(document_id: str, user_id: str):
    conn = get_connection()
    conn.execute(
        "DELETE FROM knowledge_edges WHERE source_document_id = ? AND user_id = ?",
        (document_id, user_id),
    )
    conn.commit()
    conn.close()


def insert_edge(
    edge_id: str,
    user_id: str,
    source_node_id: str,
    target_node_id: str,
    source_document_id: str,
    target_document_id: str,
    relation_type: str,
    similarity_score: float,
    evidence: dict,
    status: str = "accepted",
) -> dict:
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        INSERT INTO knowledge_edges
        (edge_id, user_id, source_node_id, target_node_id, source_document_id,
         target_document_id, relation_type, similarity_score, evidence_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            edge_id, user_id, source_node_id, target_node_id, source_document_id,
            target_document_id, relation_type, similarity_score,
            json.dumps(evidence, ensure_ascii=False), status, now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM knowledge_edges WHERE edge_id = ?", (edge_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_edges_for_source_document(document_id: str, user_id: str, status: str | None = None) -> list[dict]:
    conn = get_connection()
    if status:
        rows = conn.execute(
            """
            SELECT * FROM knowledge_edges
            WHERE source_document_id = ? AND user_id = ? AND status = ?
            ORDER BY similarity_score DESC
            """,
            (document_id, user_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM knowledge_edges
            WHERE source_document_id = ? AND user_id = ?
            ORDER BY similarity_score DESC
            """,
            (document_id, user_id),
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("labels_json", "evidence_json", "input_snapshot"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except json.JSONDecodeError:
                d[key] = None
    return d
