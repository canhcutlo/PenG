"""Background processing for uploaded documents."""
import asyncio
import logging
from app.db.sqlite_store import (
    update_job,
    update_document_status,
    log_activity,
    get_document,
)
from app.services.extractor import extract, get_text_from_result
from app.services.file_storage import get_document_file_path
from app.services.artifacts import generate_artifacts_for_document
from app.services.chunk_indexing import index_document_chunks
from app.config import settings

logger = logging.getLogger(__name__)


async def process_document(doc_id: str, job_id: str, user_id: str):
    """Process a document: extract text, index into RAG, generate artifacts, then update status."""
    try:
        update_job(job_id, "processing", progress=10)

        doc = get_document(doc_id, user_id)
        if not doc:
            update_job(job_id, "failed", progress=0, error_message="Document not found")
            return

        file_path = get_document_file_path(doc_id)
        category = doc["category"]

        update_job(job_id, "processing", progress=30)
        result = await extract(str(file_path), category)
        text = get_text_from_result(result)
        if not text.strip():
            raise ValueError("No text extracted from document")

        if settings.index_on_upload:
            update_job(job_id, "processing", progress=60)
            from app.services.rag import index_document
            await index_document(doc_id, text, user_id=user_id)
            await index_document_chunks(doc_id, text, user_id, category)
            logger.info("Indexed document %s for user %s (%d chars)", doc_id, user_id, len(text))

        update_job(job_id, "processing", progress=85)
        try:
            await generate_artifacts_for_document(doc_id, user_id, text)
        except Exception as exc:
            logger.warning("Artifact generation failed for doc %s (non-fatal): %s", doc_id, exc)

        update_job(job_id, "processing", progress=90)
        update_document_status(doc_id, "completed")
        update_job(job_id, "completed", progress=100)
        log_activity(
            doc_id,
            "uploaded",
            user_id,
            {"text_length": len(text), "category": category},
        )

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {str(exc)}"
        logger.error("Processing failed for doc %s: %s", doc_id, error_message)
        update_document_status(doc_id, "failed")
        update_job(job_id, "failed", progress=0, error_message=error_message)


def process_document_sync(doc_id: str, job_id: str, user_id: str):
    """Run processing from FastAPI's threadpool."""
    asyncio.run(process_document(doc_id, job_id, user_id))
