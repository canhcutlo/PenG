# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Summary generation with versioned prompt and validation."""
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator
from app.services.structured import generate_structured

SUMMARY_PROMPT_VERSION = "v2"

SUMMARY_SYSTEM = "Tóm tắt chính xác nội dung nguồn. Chỉ trả về JSON theo schema."

SUMMARY_PROMPT = """Tóm tắt nội dung sau thành 4-8 ý chính (mỗi ý dưới 25 từ).
Chỉ trả về JSON theo đúng định dạng sau, không kèm bất kỳ giải thích nào:
{{
  "bullets": [
    "Ý chính 1...",
    "Ý chính 2...",
    "Ý chính 3..."
  ]
}}

Nội dung:
{text}"""


class SummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"bullets": [str(item) for item in data if str(item).strip()]}
        if isinstance(data, dict):
            for key in ["bullets", "summary", "points", "items", "y_chinh", "main_points", "ideas", "key_points"]:
                val = data.get(key)
                if isinstance(val, list):
                    return {"bullets": [str(item) for item in val if str(item).strip()]}
                if isinstance(val, str) and val.strip():
                    lines = [line.strip().lstrip("-*123456789. ") for line in val.splitlines() if line.strip()]
                    if lines:
                        return {"bullets": lines}
        return data

    @field_validator("bullets")
    @classmethod
    def bullets_not_empty(cls, v: list[str]) -> list[str]:
        for b in v:
            if not b or len(b.strip()) < 3:
                raise ValueError("Each bullet must be at least 3 characters")
        return v


async def generate_summary(text: str, max_retries: int = 2) -> str:
    """Generate a validated Markdown summary from text, falling back to deterministic extraction."""
    try:
        summary = await generate_structured(
            SUMMARY_PROMPT.format(text=text[:4000]),
            SummaryOutput,
            system_prompt=SUMMARY_SYSTEM,
            max_retries=max_retries,
            use_instructor=False,
            max_new_tokens=384,
        )
        return _format_summary(summary.bullets)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Summary LLM generation failed, using fallback: %s", exc)
        return build_fallback_summary(text)


def build_fallback_summary(text: str) -> str:
    """Extract 4-6 key sentences or bullets directly from document paragraphs."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    bullets: list[str] = []

    # Check for existing bullet points first
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            cleaned = line.lstrip("-*• ").strip()
            if len(cleaned) >= 10 and cleaned not in bullets:
                bullets.append(cleaned[:180])
            if len(bullets) >= 6:
                break

    # If not enough bullets, extract the first sentence of each paragraph
    if len(bullets) < 4:
        for part in parts:
            clean_part = re.sub(r"^#+\s+.*$", "", part, flags=re.MULTILINE).strip()
            if not clean_part:
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?;\n])\s+", clean_part) if len(s.strip()) >= 10]
            for s in sentences:
                cleaned_s = re.sub(r"\s+", " ", s).strip(" -*│┌┐└┘─#")
                if cleaned_s and cleaned_s not in bullets:
                    bullets.append(cleaned_s[:180])
                    break
            if len(bullets) >= 6:
                break

    if not bullets:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?;\n])\s+", text) if len(s.strip()) >= 5]
        bullets = [s[:180] for s in sentences[:6]]

    if not bullets:
        bullets = [text[:180].strip() or "Nội dung tài liệu"]

    return _format_summary(bullets[:8])


def _format_summary(bullets: list[str]) -> str:
    return "\n".join(f"- {b.strip()}" for b in bullets)


def validate_summary_markdown(markdown: str) -> bool:
    """Quick structural validation for summary Markdown."""
    bullets = [line for line in markdown.splitlines() if line.strip().startswith("-")]
    return 1 <= len(bullets) <= 8
