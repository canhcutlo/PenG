"""Orchestrates extraction pipeline: detect content type, route to appropriate service."""
from app.services.stt import transcribe_audio
from app.services.ocr import ocr_image, extract_native_pdf_text
from app.services.video import analyze_video


async def extract(file_path: str, category: str) -> dict:
    """Extract text from any supported file type. Returns dict with text + metadata."""
    if category == "audio":
        return await transcribe_audio(file_path)
    elif category == "image":
        text = await ocr_image(file_path)
        return {"text": text, "pages": 1}
    elif category == "pdf":
        text = await extract_native_pdf_text(file_path)
        return {"text": text, "pages": 1}
    elif category == "video":
        return await analyze_video(file_path)
    else:
        raise ValueError(f"Unsupported category: {category}")


def get_text_from_result(result: dict) -> str:
    """Get plain text from extraction result."""
    if isinstance(result, dict):
        return result.get("text", "")
    return str(result)
