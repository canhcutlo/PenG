# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Lightweight application health checks."""
from app.db.sqlite_store import get_connection


def database_status() -> str:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")
        return "ok"
    except Exception:
        return "error"
