"""Document artifact generation: summary and mindmap."""
import asyncio
import hashlib
import uuid
import logging
from app.config import settings
from app.db.sqlite_store import log_activity
from app.db.artifact_store import (
    insert_artifact,
    update_artifact_status,
    get_latest_artifact,
    count_artifacts,
)
from app.services.summary_gen import generate_summary, SUMMARY_PROMPT_VERSION, validate_summary_markdown
from app.services.mindmap_gen import generate_mindmap_markdown, validate_mindmap_structure
from app.services.llm import device_info
from app.services.knowledge import update_knowledge_node_from_artifacts

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 6000
_ATTEMPTS = 3

_generation_lock = asyncio.Lock()
_gpu_semaphore = asyncio.Semaphore(1)


async def generate_artifacts_for_document(
    doc_id: str,
    user_id: str,
    text: str,
    progress_callback: callable | None = None,
):
    """Generate summary and mindmap artifacts for a document. Failures are logged but not raised."""
    if progress_callback:
        await progress_callback("generating_summary", "Đang tạo tóm tắt", 70)
    await _generate_artifact(doc_id, user_id, text, "summary", generate_summary)
    if progress_callback:
        await progress_callback("generating_mindmap", "Đang tạo mindmap", 82)
    await _generate_artifact(doc_id, user_id, text, "mindmap", generate_mindmap_markdown)


async def regenerate_artifact(doc_id: str, user_id: str, artifact_type: str) -> dict:
    """Regenerate an artifact and return the new row."""
    text = await _get_document_text(doc_id)
    if artifact_type == "summary":
        generator = generate_summary
    elif artifact_type == "mindmap":
        generator = generate_mindmap_markdown
    else:
        raise ValueError(f"Unknown artifact type: {artifact_type}")

    return await _generate_artifact(doc_id, user_id, text, artifact_type, generator)


async def _generate_artifact(doc_id: str, user_id: str, text: str, artifact_type: str, generator) -> dict:
    """Generate one artifact with bounded retries; preserve old completed artifacts on failure."""
    async with _generation_lock:
        version = count_artifacts(doc_id, artifact_type) + 1

    truncated = len(text) > _MAX_INPUT_CHARS
    input_text = text[:_MAX_INPUT_CHARS]
    input_snapshot = {
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_count": len(text),
        "truncated": truncated,
        "source_job": "extract",
    }

    artifact_id = uuid.uuid4().hex[:12]
    artifact = insert_artifact(
        artifact_id=artifact_id,
        doc_id=doc_id,
        user_id=user_id,
        artifact_type=artifact_type,
        version=version,
        status="processing",
        input_snapshot=input_snapshot,
        language=_detect_language(input_text),
        model_id=settings.llm_model,
        llm_config=device_info(),
        generation_params={"max_input_chars": _MAX_INPUT_CHARS, "max_retries": _ATTEMPTS},
        prompt_version=SUMMARY_PROMPT_VERSION if artifact_type == "summary" else "mindmap_v1",
    )

    try:
        async with _gpu_semaphore:
            content = await generator(input_text, max_retries=_ATTEMPTS) if artifact_type == "summary" else await generator(input_text)
        if artifact_type == "summary" and not validate_summary_markdown(content):
            raise ValueError("Summary validation failed")
        if artifact_type == "mindmap" and not validate_mindmap_structure(content):
            raise ValueError("Mindmap structural validation failed")

        update_artifact_status(artifact_id, "completed", content=content, attempts=1)
        log_activity(doc_id, f"{artifact_type}_generated", user_id,
                     {"artifact_id": artifact_id, "version": version})
        artifact["status"] = "completed"
        artifact["content"] = content

        try:
            await update_knowledge_node_from_artifacts(doc_id, user_id)
        except Exception as exc:
            logger.warning("Knowledge node update failed for doc %s (non-fatal): %s", doc_id, exc)

        return artifact
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {str(exc)}"
        logger.warning("Artifact %s generation failed for doc %s: %s", artifact_type, doc_id, error_message)
        update_artifact_status(artifact_id, "failed", error_message=error_message, attempts=_ATTEMPTS)
        log_activity(doc_id, "artifact_failed", user_id,
                     {"artifact_type": artifact_type, "artifact_id": artifact_id, "error": error_message})
        artifact["status"] = "failed"
        artifact["error_message"] = error_message
        return artifact


async def _get_document_text(doc_id: str) -> str:
    from app.services.file_storage import get_document_file_path
    from app.services.extractor import extract, get_text_from_result
    from app.db.sqlite_store import get_document

    doc = get_document(doc_id)
    if not doc:
        raise ValueError(f"Document {doc_id} not found")
    file_path = get_document_file_path(doc_id)
    result = await extract(str(file_path), doc["category"])
    text = get_text_from_result(result)
    if not text.strip():
        raise ValueError("No text extracted from document")
    return text


def _detect_language(text: str) -> str:
    """Simple heuristic to detect Vietnamese vs English."""
    vietnamese_marks = sum(1 for c in text if c in "àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ")
    return "vi" if vietnamese_marks > 5 else "en"
