"""OCR for images and PDFs via pytesseract/easyocr, with optional Surya."""
import os
import io
from pathlib import Path
import fitz
from PIL import Image
from app.config import settings

OCR_ENGINE = settings.ocr_engine


async def ocr_image(image_path: str) -> str:
    """OCR a single image."""
    if OCR_ENGINE == "surya":
        return await _surya_ocr_image(image_path)
    elif OCR_ENGINE == "easyocr":
        return await _easyocr_image(image_path)
    else:
        return await _tesseract_ocr(image_path)


async def ocr_pdf(pdf_path: str) -> str:
    """OCR all pages of a PDF."""
    if OCR_ENGINE == "surya":
        return await _surya_ocr_pdf(pdf_path)
    elif OCR_ENGINE == "easyocr":
        return await _easyocr_pdf(pdf_path)
    else:
        return await _tesseract_ocr_pdf(pdf_path)




async def _tesseract_ocr(image_path: str) -> str:
    import pytesseract

    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang="vie+eng").strip()


async def _tesseract_ocr_pdf(pdf_path: str) -> str:
    import pytesseract

    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        img = _page_to_image(page)
        text = pytesseract.image_to_string(img, lang="vie+eng").strip()
        if text:
            texts.append(f"[Page {page.number + 1}]\n{text}")
    doc.close()
    return "\n\n".join(texts)




_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
    return _easyocr_reader


async def _easyocr_image(image_path: str) -> str:
    reader = _get_easyocr_reader()
    results = reader.readtext(image_path, detail=0)
    return "\n".join(results)


async def _easyocr_pdf(pdf_path: str) -> str:
    reader = _get_easyocr_reader()
    doc = fitz.open(pdf_path)
    page_texts = []
    for page in doc:
        img = _page_to_image(page)
        temp_path = f"{pdf_path}_page_{page.number}.png"
        img.save(temp_path)
        results = reader.readtext(temp_path, detail=0)
        os.remove(temp_path)
        text = "\n".join(results)
        if text:
            page_texts.append(f"[Page {page.number + 1}]\n{text}")
    doc.close()
    return "\n\n".join(page_texts)




async def _surya_ocr_image(image_path: str) -> str:
    from surya.ocr import run_ocr
    from surya.model.detection.model import load_model as load_det_model, load_processor as load_det_processor
    from surya.model.recognition.model import load_model as load_rec_model
    from surya.model.recognition.processor import load_processor as load_rec_processor

    det_model, det_processor = load_det_model(), load_det_processor()
    rec_model, rec_processor = load_rec_model(), load_rec_processor()

    langs = ["vi", "en"]
    predictions = run_ocr(
        [image_path], [langs],
        det_model=det_model, det_processor=det_processor,
        rec_model=rec_model, rec_processor=rec_processor,
    )
    return "\n".join(p.text for p in predictions[0])


async def _surya_ocr_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        img = _page_to_image(page)
        temp_path = f"{pdf_path}_page_{page.number}.png"
        img.save(temp_path)
        texts.append(await _surya_ocr_image(temp_path))
        os.remove(temp_path)
    doc.close()
    return "\n\n".join(texts)




def _page_to_image(page, dpi: int = 200) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png")))


async def extract_native_pdf_text(pdf_path: str) -> str:
    """Extract text embedded in PDF first; fall back to OCR if needed."""
    doc = fitz.open(pdf_path)
    page_texts = []
    for page in doc:
        text = page.get_text().strip()
        page_texts.append((page.number, text))
    doc.close()

    non_empty = sum(1 for _, t in page_texts if t)
    if non_empty >= len(page_texts) * 0.5:
        return "\n\n".join(
            f"[Page {num + 1}]\n{text}" if text else ""
            for num, text in page_texts
        ).strip()

    return await ocr_pdf(pdf_path)
