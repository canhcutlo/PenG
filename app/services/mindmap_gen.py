"""Mindmap generation from document text using LLM, with sanitization."""
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
