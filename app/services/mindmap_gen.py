# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Mindmap generation from document text using LLM, with sanitization and validation."""
import re
from app.services.llm import complete
from app.services.prompts import build_mindmap_prompt

DANGEROUS_PATTERN = re.compile(r"<[^>]+>|```|~~~", re.IGNORECASE)
MAX_DEPTH_HEADERS = 3


async def generate_mindmap_markdown(text: str) -> str:
    """Generate and sanitize a mindmap Markdown from text."""
    prompt = build_mindmap_prompt(text)
    raw = await complete(prompt, max_new_tokens=512, raise_on_error=True)
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
    """Validate a bounded Markdown tree with populated H2 branches."""
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines or not re.match(r"^#\s+\S", lines[0]):
        return False

    h1_count = 0
    branch_count = 0
    current_bullets = None
    for line in lines:
        if re.match(r"^#\s+\S", line):
            h1_count += 1
            if h1_count > 1 or branch_count:
                return False
        elif re.match(r"^##\s+\S", line):
            if current_bullets is not None and not (2 <= current_bullets <= 5):
                return False
            branch_count += 1
            current_bullets = 0
        elif re.match(r"^-\s+\S", line):
            if current_bullets is None:
                return False
            current_bullets += 1
        elif re.match(r"^#{3,}\s+\S", line) or not line.startswith("#"):
            return False
        else:
            return False

    return h1_count == 1 and 3 <= branch_count <= 7 and current_bullets is not None and 2 <= current_bullets <= 5
