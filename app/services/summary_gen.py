# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Summary generation with versioned prompt and validation."""
import re
from pydantic import BaseModel, Field, field_validator
from app.services.structured import generate_structured

SUMMARY_PROMPT_VERSION = "v1"

SUMMARY_SYSTEM = "Tóm tắt chính xác nội dung nguồn. Chỉ trả về JSON theo schema."

SUMMARY_PROMPT = """Tóm tắt nội dung thành 4-8 ý chính.
- Mỗi ý tối đa 25 từ.
- Giữ ngôn ngữ của nội dung.
- Không thêm thông tin ngoài nguồn.

Nội dung:
{text}"""


class SummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=1, max_length=8)

    @field_validator("bullets")
    @classmethod
    def bullets_not_empty(cls, v: list[str]) -> list[str]:
        for b in v:
            if not b or len(b.strip()) < 3:
                raise ValueError("Each bullet must be at least 3 characters")
        return v


async def generate_summary(text: str, max_retries: int = 2) -> str:
    """Generate a validated Markdown summary from text."""
    summary = await generate_structured(
        SUMMARY_PROMPT.format(text=text[:4000]),
        SummaryOutput,
        system_prompt=SUMMARY_SYSTEM,
        max_retries=max_retries,
        use_instructor=False,
        max_new_tokens=384,
    )
    return _format_summary(summary.bullets)


def _format_summary(bullets: list[str]) -> str:
    return "\n".join(f"- {b.strip()}" for b in bullets)


def validate_summary_markdown(markdown: str) -> bool:
    """Quick structural validation for summary Markdown."""
    bullets = [line for line in markdown.splitlines() if line.strip().startswith("-")]
    return 1 <= len(bullets) <= 8
