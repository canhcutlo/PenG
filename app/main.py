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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
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

    app.include_router(upload.router, prefix="/api", tags=["Upload"])
    app.include_router(query.router, prefix="/api", tags=["Query"])
    app.include_router(quiz.router, prefix="/api", tags=["Quiz"])
    app.include_router(mindmap.router, prefix="/api", tags=["Mindmap"])
    app.include_router(history.router, prefix="/api", tags=["History"])

    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()
