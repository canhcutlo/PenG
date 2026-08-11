"""Summary generation with versioned prompt and validation."""
import re
from pydantic import BaseModel, Field, ValidationError, field_validator
from app.services.llm import complete
from app.services.structured import _extract_json, GenerationError

SUMMARY_PROMPT_VERSION = "v1"

SUMMARY_SYSTEM = (
    "Bạn là trợ lý học tập. Tóm tắt nội dung sau thành các ý chính dạng bullet points. "
    "Trả về JSON theo schema được cung cấp."
)

SUMMARY_PROMPT = """Tóm tắt tài liệu sau thành các ý chính dạng bullet points.
- Mỗi bullet tối đa 25 từ.
- Tối đa 8 bullets.
- Dùng tiếng Việt nếu văn bản tiếng Việt.
- Không lai ngôn ngữ vô lý, không thêm thông tin không có trong văn bản.

Text:
{text}

Trả về JSON đúng schema:
{{"bullets": ["ý 1", "ý 2", ...]}}"""


class SummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=1, max_length=8)

    @field_validator("bullets")
    @classmethod
    def bullets_not_empty(cls, v: list[str]) -> list[str]:
        for b in v:
            if not b or len(b.strip()) < 3:
                raise ValueError("Each bullet must be at least 3 characters")
        return v


async def generate_summary(text: str, max_retries: int = 3) -> str:
    """Generate a validated Markdown summary from text."""
    prompt = SUMMARY_PROMPT.format(text=text[:6000])
    last_error = None
    for attempt in range(max_retries):
        try:
            raw = await complete(prompt, system_prompt=SUMMARY_SYSTEM, max_new_tokens=1024)
            data = _extract_json(raw)
            summary = SummaryOutput.model_validate(data)
            return _format_summary(summary.bullets)
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            prompt = prompt + f"\n\nPrevious response invalid: {last_error}. Fix it."

    raise GenerationError(f"Summary generation failed: {last_error}")


def _format_summary(bullets: list[str]) -> str:
    return "\n".join(f"- {b.strip()}" for b in bullets)


def validate_summary_markdown(markdown: str) -> bool:
    """Quick structural validation for summary Markdown."""
    bullets = [line for line in markdown.splitlines() if line.strip().startswith("-")]
    return 1 <= len(bullets) <= 8
