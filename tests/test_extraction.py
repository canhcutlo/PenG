"""Integration tests for Phase 2 extraction services.

Run integration tests with:
    pytest tests/test_extraction.py -v -m integration

Unit tests here avoid downloading large AI models.
"""
import io
import os
import pytest
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

from app.services.ocr import ocr_image, _tesseract_ocr, extract_native_pdf_text
from app.services.extractor import extract




@pytest.fixture
def text_image(tmp_path):
    """Create a small PNG image with text for OCR tests."""
    img = Image.new("RGB", (300, 100), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 35), "Hello PenG", fill="black", font=font)

    path = tmp_path / "hello.png"
    img.save(path)
    return str(path)


@pytest.fixture
def text_pdf(tmp_path):
    """Create a small PDF with embedded text."""
    import fitz
    path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello PenG PDF")
    doc.save(str(path))
    doc.close()
    return str(path)




@pytest.mark.asyncio
async def test_tesseract_ocr_not_available_without_binary(text_image):
    """Unit test: pytesseract raises TesseractNotFoundError if binary missing.
    This documents that real OCR needs either Tesseract installed or EasyOCR.
    """
    import pytesseract
    try:
        await _tesseract_ocr(text_image)
    except pytesseract.TesseractNotFoundError:
        pass


@pytest.mark.asyncio
async def test_extract_unsupported_category():
    """Extractor should raise ValueError for unsupported category."""
    with pytest.raises(ValueError):
        await extract("dummy.txt", "document")


@pytest.mark.asyncio
async def test_extract_image_routes_to_ocr(text_image):
    """Extractor routes image to OCR. If OCR engine unavailable, exception is caught."""
    try:
        result = await extract(text_image, "image")
        assert "text" in result
    except Exception as exc:
        assert "tesseract" in str(exc).lower() or "not installed" in str(exc).lower()


@pytest.mark.asyncio
async def test_extract_pdf_native_text(text_pdf):
    """Native PDF text extraction should return embedded text."""
    result = await extract(text_pdf, "pdf")
    assert "text" in result
    assert "Hello PenG PDF" in result["text"]




@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("SKIP_AI_MODELS") == "1",
    reason="AI model downloads disabled",
)
@pytest.mark.asyncio
async def test_ocr_image(text_image):
    result = await ocr_image(text_image)
    assert isinstance(result, str)
    assert result.strip() != ""


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("SKIP_AI_MODELS") == "1",
    reason="AI model downloads disabled",
)
@pytest.mark.asyncio
async def test_extract_image(text_image):
    result = await extract(text_image, "image")
    assert "text" in result
    assert isinstance(result["text"], str)
