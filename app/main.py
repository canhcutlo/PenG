# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings, PROJECT_ROOT
from app.routers import (
    upload,
    query,
    quiz,
    mindmap,
    history,
    auth,
    documents,
    chat,
    knowledge,
)
from app.db.sqlite_store import init_sqlite


STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_sqlite()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
    if settings.auth_cookie_secure:
        origins.append("https://*.ngrok-free.app")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    async def health():
        from app.db.sqlite_store import get_connection
        try:
            conn = get_connection()
            conn.execute("SELECT 1")
            conn.close()
            db_status = "ok"
        except Exception:
            db_status = "error"
        return {"status": "ok", "db": db_status}

    app.include_router(auth.router, prefix="/api", tags=["Auth"])
    app.include_router(upload.router, prefix="/api", tags=["Upload"])
    app.include_router(query.router, prefix="/api", tags=["Query"])
    app.include_router(quiz.router, prefix="/api", tags=["Quiz"])
    app.include_router(mindmap.router, prefix="/api", tags=["Mindmap"])
    app.include_router(history.router, prefix="/api", tags=["History"])
    app.include_router(documents.router, prefix="/api", tags=["Documents"])
    app.include_router(chat.router, prefix="/api", tags=["Chat"])
    app.include_router(knowledge.router, prefix="/api", tags=["Knowledge"])

    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()


def run_server():
    """Entrypoint for the `peng-server` CLI command."""
    import argparse
    import os
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the PenG server.")
    parser.add_argument(
        "--host",
        default=os.getenv("PENG_HOST", "127.0.0.1"),
        help="Bind socket to this host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PENG_PORT", "8000")),
        help="Bind socket to this port (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("PENG_RELOAD", "false").lower() in ("true", "1", "yes"),
        help="Enable auto-reload",
    )
    args, _ = parser.parse_known_args()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    run_server()

