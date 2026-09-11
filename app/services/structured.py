# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Structured output generation with validation and bounded retry.

Two paths:
1. **JSON + Pydantic** (default): call the local LLM, ask for JSON, parse,
   validate with a Pydantic model, retry with error feedback. Works with any
   model (Transformers/Qwen/Llama) without an OpenAI-compatible adapter.
2. **Instructor** (optional): used only when an OpenAI-compatible endpoint is
   configured (e.g. Ollama/vLLM in Colab). Activated via `use_instructor=True`.

Retry is bounded: MAX_RETRIES attempts, then raise GenerationError.
"""
import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services.llm import complete

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3

completion_func = complete


class GenerationError(Exception):
    """Raised when structured generation fails after bounded retries."""

    def __init__(self, message: str, reason: str = "validation", detail: str = ""):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or message


def _extract_json(raw: str) -> dict:
    """Parse JSON from LLM output, tolerating code fences and surrounding text."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")

    return json.loads(text[start : end + 1], strict=False)


async def generate_structured(
    prompt: str,
    response_model: Type[T],
    system_prompt: str | None = None,
    max_retries: int = MAX_RETRIES,
    use_instructor: bool | None = None,
    max_new_tokens: int = 512,
    response_schema: dict | None = None,
) -> T:
    """Generate and validate a schema-constrained response."""
    use_instructor = settings.use_instructor if use_instructor is None else use_instructor

    if use_instructor:
        return await _generate_with_instructor(prompt, response_model, system_prompt)

    error_hint = None
    last_reason = "validation"
    for attempt in range(max_retries):
        full_prompt = prompt if error_hint is None else (
            f"{prompt}\n\nFix this validation error: {error_hint}"
        )
        try:
            raw = await completion_func(
                full_prompt,
                system_prompt=system_prompt or _default_system_prompt(response_model),
                max_new_tokens=max_new_tokens,
                response_schema=response_schema or response_model.model_json_schema(),
                raise_on_error=True,
            )
            data = _extract_json(raw)
            return response_model.model_validate(data)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            error_hint = _format_validation_error(exc)
            last_reason = "invalid_output"
            logger.warning("Structured generation attempt %d failed: %s", attempt + 1, error_hint)
        except RuntimeError as exc:
            error_hint = str(exc)
            last_reason = "runtime"
            logger.error("Structured generation runtime failure: %s", error_hint)
            break

    raise GenerationError(
        f"Failed to generate valid {response_model.__name__}",
        reason=last_reason,
        detail=error_hint or "Unknown structured generation failure",
    )


async def _generate_with_instructor(
    prompt: str,
    response_model: Type[T],
    system_prompt: str | None,
) -> T:
    """Use Instructor with an OpenAI-compatible client (requires endpoint)."""
    try:
        from instructor.v2.providers.litellm.client import from_litellm
    except ImportError:
        raise GenerationError("Instructor adapter not available (instructor/litellm missing)")

    raise GenerationError(
        "Instructor with local model requires an OpenAI-compatible endpoint "
        "(Ollama/vLLM) configured via settings; not yet enabled in this runtime."
    )


def _default_system_prompt(response_model: Type[T]) -> str:
    return (
        f"You are a precise data generator. Respond with ONLY valid JSON matching "
        f"this schema: {response_model.model_json_schema()}. No extra text, no markdown."
    )


def _format_validation_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        try:
            return f"Validation error: {json.dumps(exc.errors(), ensure_ascii=False, default=str)}"
        except (TypeError, ValueError):
            return f"Validation error: {str(exc)}"
    return f"{type(exc).__name__}: {str(exc)}"
