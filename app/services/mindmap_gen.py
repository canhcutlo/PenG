"""Mindmap generation from document text using LLM, with sanitization and validation."""
import re
from app.services.llm import complete
from app.services.prompts import build_mindmap_prompt

DANGEROUS_PATTERN = re.compile(r"<[^>]+>|```|~~~", re.IGNORECASE)
MAX_DEPTH_HEADERS = 3


async def generate_mindmap_markdown(text: str) -> str:
    """Generate and sanitize a mindmap Markdown from text."""
    prompt = build_mindmap_prompt(text)
    raw = await complete(prompt, max_new_tokens=1024)
    return sanitize_mindmap(raw)


def sanitize_mindmap(raw: str) -> str:
    """Remove dangerous HTML/code fences and enforce max header depth."""
    cleaned = DANGEROUS_PATTERN.sub("", raw)

    lines = []
    for line in cleaned.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            hashes = "#" * min(len(m.group(1)), MAX_DEPTH_HEADERS)
            lines.append(f"{hashes} {m.group(2)}")
        else:
            lines.append(line)

    return "\n".join(lines).strip()


def validate_mindmap_structure(markdown: str) -> bool:
    """Validate one H1, 3-7 H2, and 2-5 bullets per H2 branch."""
    lines = [line.rstrip() for line in markdown.splitlines()]

    h1_count = sum(1 for line in lines if re.match(r"^#\s+\S", line))
    if h1_count != 1:
        return False

    h2_headers = [line for line in lines if re.match(r"^##\s+\S", line)]
    if not (3 <= len(h2_headers) <= 7):
        return False

    current_bullets = 0
    for line in lines:
        if re.match(r"^##\s+\S", line):
            if current_bullets > 0 and not (2 <= current_bullets <= 5):
                return False
            current_bullets = 0
        elif re.match(r"^-\s+\S", line):
            current_bullets += 1

    if current_bullets > 0 and not (2 <= current_bullets <= 5):
        return False

    return True
