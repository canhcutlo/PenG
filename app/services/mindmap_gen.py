# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Mindmap generation from document text using LLM, with sanitization and validation."""
import re
from app.services.llm import complete
from app.services.prompts import build_mindmap_prompt

DANGEROUS_PATTERN = re.compile(r"<[^>]+>|```|~~~", re.IGNORECASE)
TOP_LEVEL_HEADING = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
SUB_HEADING = re.compile(r"^\s*\d+\.\d+\.\s+(.+?)\s*$")
MAX_DEPTH_HEADERS = 3


async def generate_mindmap_markdown(text: str) -> str:
    """Generate a valid mindmap, falling back to deterministic source structure."""
    prompt = build_mindmap_prompt(text)
    raw = await complete(prompt, max_new_tokens=768, raise_on_error=True)
    markdown = sanitize_mindmap(raw)
    if validate_mindmap_structure(markdown):
        return markdown
    fallback_title = next(
        (match.group(1).strip() for line in markdown.splitlines() if (match := re.match(r"^#\s+(.+)$", line))),
        None,
    )
    return build_fallback_mindmap(text, fallback_title=fallback_title)


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


def build_fallback_mindmap(text: str, fallback_title: str | None = None) -> str:
    """Build a bounded Markdown tree directly from source sections without dummy text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = fallback_title or next((line for line in lines if not line.startswith(("[", "*"))), "Tài liệu")
    title = title.lstrip("\ufeff# ").strip() or "Tài liệu"
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None

    for line in lines:
        top = TOP_LEVEL_HEADING.match(line)
        top_md = re.match(r"^##\s+(?:(\d+[\.\)]\s+)?(.+?))\s*$", line)
        sub = SUB_HEADING.match(line)
        sub_md = re.match(r"^###\s+(?:(\d+[\.\)]\s+)?(.+?))\s*$", line)

        if top:
            current = (top.group(2), [])
            sections.append(current)
        elif top_md:
            current = (top_md.group(2), [])
            sections.append(current)
        elif current is not None and (sub or sub_md):
            heading_text = sub.group(1) if sub else sub_md.group(2)
            current[1].append(heading_text)
        elif current is not None and not line.startswith(("[", "#", "↓", "→")):
            current[1].append(line.lstrip("*- ").strip())

    sections = [(heading, items) for heading, items in sections if heading and items]
    if len(sections) < 3:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        sections = [(f"Phần {index + 1}", [part]) for index, part in enumerate(paragraphs[:7])]

    sections = sections[:7]
    while len(sections) < 3:
        sections.append((f"Tổng quan {len(sections) + 1}", [text[:240]]))

    output = [f"# {title.lstrip('# ').strip()}"]
    for heading, items in sections:
        candidate_bullets: list[str] = []
        for item in items:
            sub_parts = [p.strip() for p in re.split(r"(?<=[.!?;\n])\s+", item) if p.strip()]
            for sp in sub_parts:
                cleaned = re.sub(r"\s+", " ", sp).strip(" -*│┌┐└┘─#")
                if cleaned and cleaned not in candidate_bullets and cleaned != heading:
                    candidate_bullets.append(cleaned[:240])
            if not sub_parts and item.strip():
                cleaned = re.sub(r"\s+", " ", item).strip(" -*│┌┐└┘─#")
                if cleaned and cleaned not in candidate_bullets and cleaned != heading:
                    candidate_bullets.append(cleaned[:240])

        bullets: list[str] = candidate_bullets[:5]

        if len(bullets) < 2:
            for item in items:
                clauses = [c.strip() for c in re.split(r"[,;—–]\s*", item) if len(c.strip()) >= 3]
                for clause in clauses:
                    cleaned_c = re.sub(r"\s+", " ", clause).strip(" -*│┌┐└┘─#")
                    if cleaned_c and cleaned_c not in bullets and cleaned_c != heading:
                        bullets.append(cleaned_c[:240])
                        if len(bullets) >= 2:
                            break
                if len(bullets) >= 2:
                    break

        if len(bullets) < 2:
            doc_sentences = [
                re.sub(r"\s+", " ", s).strip(" -*│┌┐└┘─#")
                for s in re.split(r"(?<=[.!?;\n])\s+", text)
                if len(re.sub(r"\s+", " ", s).strip(" -*│┌┐└┘─#")) >= 3
            ]
            for ds in doc_sentences:
                if ds not in bullets and heading not in ds and not ds.startswith("#"):
                    bullets.append(ds[:240])
                    if len(bullets) >= 2:
                        break

        while len(bullets) < 2:
            if heading and heading not in bullets:
                bullets.append(f"Ý chính: {heading}"[:240])
            else:
                fallback_chunk = text[:240].strip() or "Nội dung tài liệu"
                bullets.append(fallback_chunk)

        output.append(f"## {heading}")
        output.extend(f"- {bullet}" for bullet in bullets)

    return "\n".join(output)


def validate_mindmap_structure(markdown: str) -> bool:
    """Validate a bounded Markdown tree with reasonable branching (H1, H2, H3, bullets)."""
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines or not re.match(r"^#\s+\S", lines[0]):
        return False

    h1_count = 0
    branch_count = 0
    current_items = None

    for line in lines:
        if re.match(r"^#\s+\S", line):
            h1_count += 1
            if h1_count > 1 or branch_count > 0:
                return False
        elif re.match(r"^##\s+\S", line):
            if h1_count != 1:
                return False
            if current_items is not None and current_items < 2:
                return False
            branch_count += 1
            current_items = 0
        elif re.match(r"^###\s+\S", line):
            if current_items is None:
                return False
            current_items += 1
        elif re.match(r"^[-*]\s+\S", line):
            if current_items is None:
                return False
            current_items += 1
        else:
            return False

    if h1_count != 1 or not (3 <= branch_count <= 10) or current_items is None or current_items < 2:
        return False

    return True
