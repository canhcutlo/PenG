"""Chunking: split extracted text into chunks with metadata for indexing."""
import re
from dataclasses import dataclass, field

MAX_CHARS = 2000
OVERLAP = 200

PAGE_RE = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)
SCENE_RE = re.compile(r"\[Scene\s+(\d+)(?:\s+at\s+([\d.]+)s)?\]", re.IGNORECASE)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    page: int | None = None
    scene: int | None = None
    timestamp: float | None = None
    metadata: dict = field(default_factory=dict)


def _split_into_blocks(text: str) -> list[str]:
    """Split text into logical blocks: by headers, blank lines, or fallback to paragraphs."""
    parts = re.split(r"(?=\[Page \d+\])|(?=\[Scene \d+)", text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 1:
        return parts
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def split_text(text: str) -> list[str]:
    """Return logical blocks without size limits."""
    return _split_into_blocks(text)


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Chunk text by size with overlap, preferring sentence boundaries."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            cut = _find_sentence_boundary(text, start, end)
            if cut is not None:
                end = cut
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


def _find_sentence_boundary(text: str, start: int, end: int) -> int | None:
    """Find a sentence/paragraph boundary within [start, end]. Returns index or None."""
    window = text[start:end]
    for marker in ["\n\n", ".\n", ".\n\n", ". ", "? ", "! ", ";\n"]:
        idx = window.rfind(marker)
        if idx != -1 and idx > len(window) * 0.5:
            return start + idx + len(marker)
    return None


def _parse_metadata_header(block: str) -> dict:
    """Extract page/scene/timestamp from a block header."""
    meta: dict = {}
    m = PAGE_RE.search(block)
    if m:
        meta["page"] = int(m.group(1))
    m = SCENE_RE.search(block)
    if m:
        meta["scene"] = int(m.group(1))
        if m.group(2):
            meta["timestamp"] = float(m.group(2))
    return meta


def build_chunks(
    doc_id: str,
    category: str,
    text: str,
    metadata: dict | None = None,
    max_chars: int = MAX_CHARS,
    overlap: int = OVERLAP,
) -> list[dict]:
    """Build chunk dicts from extracted text, preserving page/scene/timestamp metadata."""
    result: list[dict] = []
    blocks = split_text(text)

    for block in blocks:
        header_meta = _parse_metadata_header(block)
        for i, chunk_text_part in enumerate(chunk_text(block, max_chars, overlap)):
            chunk_meta = dict(metadata or {})
            chunk_meta["category"] = category
            chunk_meta.update(header_meta)
            result.append(
                {
                    "chunk_id": f"{doc_id}:{len(result)}",
                    "doc_id": doc_id,
                    "text": chunk_text_part,
                    "page": chunk_meta.get("page"),
                    "scene": chunk_meta.get("scene"),
                    "timestamp": chunk_meta.get("timestamp"),
                    "metadata": chunk_meta,
                }
            )
    return result
