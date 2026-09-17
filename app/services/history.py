# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Learning history access."""
from app.db.sqlite_store import get_activities, get_document, get_documents_for_user, log_activity


def list_history(user_id: str, limit: int) -> list[dict]:
    documents = {row["doc_id"]: row for row in get_documents_for_user(user_id, limit=10000)}
    return [
        {
            "id": row["id"],
            "doc_id": row["doc_id"],
            "original_name": documents.get(row["doc_id"], {}).get("original_name") or row["doc_id"],
            "action": row["action"],
            "metadata": row["metadata_json"],
            "created_at": row["created_at"],
        }
        for row in get_activities(user_id, limit)
    ]


def add_history(doc_id: str, action: str, user_id: str) -> bool:
    if not get_document(doc_id, user_id):
        return False
    log_activity(doc_id, action, user_id)
    return True
