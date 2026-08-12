"""Faithfulness guard for RAG and chat answers.

The guard ensures model answers are grounded in retrieved evidence. It:

* Normalizes retrieved chunks into stable evidence items (E1, E2, ...).
* Validates model-provided evidence IDs against available evidence.
* Applies deterministic rules for high-risk eligibility/negation questions.
* Bounds correction retries and falls back to a safe answer when unsupported.

The guard never claims factual truth beyond what the supplied evidence can
support.
"""
import re
from dataclasses import dataclass

from app.models.schemas import FaithfulAnswer
from app.services.prompts import (
    FAITHFUL_ANSWER_SYSTEM,
    build_faithful_answer_prompt,
    build_faithful_chat_prompt,
)
from app.services.structured import GenerationError, generate_structured


@dataclass
class EvidenceItem:
    id: str
    doc_id: str
    chunk_id: str
    text: str
    page: int | None
    scene: int | None
    timestamp: float | None
    score: float = 0.0


_RESTRICTIVE_PATTERNS = [
    re.compile(r"\btất cả\s+sinh\s+viên\b", re.IGNORECASE),
    re.compile(r"\bchỉ\s+sinh\s+viên\b", re.IGNORECASE),
    re.compile(r"\bchỉ\s+dành\s+cho\b", re.IGNORECASE),
    re.compile(r"\bchỉ\s+áp\s+dụng\s+cho\b", re.IGNORECASE),
    re.compile(r"\bchỉ\s+dành\s+riêng\s+cho\b", re.IGNORECASE),
    re.compile(r"\bstudents\s+currently\s+enrolled\b", re.IGNORECASE),
    re.compile(r"\bonly\s+students\b", re.IGNORECASE),
    re.compile(r"\bonly\s+for\s+students\b", re.IGNORECASE),
    re.compile(r"\bonly\s+applies?\s+to\s+students\b", re.IGNORECASE),
    re.compile(r"\brestricted\s+to\s+students\b", re.IGNORECASE),
]

_OUTSIDER_VI_PATTERNS = [
    re.compile(r"\bngườ[iI]\s+ngoài\b", re.IGNORECASE),
    re.compile(r"\bngườ[iI]\s+lạ\b", re.IGNORECASE),
    re.compile(r"\bbên\s+ngoài\b", re.IGNORECASE),
    re.compile(r"\bngoài\s+trường\b", re.IGNORECASE),
    re.compile(r"\bkhông\s+phải\s+sinh\s+viên\b", re.IGNORECASE),
    re.compile(r"\bkhông\s+phải\s+là\s+sinh\s+viên\b", re.IGNORECASE),
    re.compile(r"\bkhách\b", re.IGNORECASE),
]

_OUTSIDER_EN_PATTERNS = [
    re.compile(r"\boutsiders?\b", re.IGNORECASE),
    re.compile(r"\bexternal\b", re.IGNORECASE),
    re.compile(r"\bnon[-\s]?students?\b", re.IGNORECASE),
    re.compile(r"\bnot\s+a\s+student\b", re.IGNORECASE),
    re.compile(r"\boutside\s+(?:the\s+)?(?:university|school|college)\b", re.IGNORECASE),
    re.compile(r"\bnon[-\s]?member\b", re.IGNORECASE),
]

_OUTSIDER_PATTERNS = _OUTSIDER_VI_PATTERNS + _OUTSIDER_EN_PATTERNS

_AFFIRMATIVE_MARKERS = [
    re.compile(r"\bđúng\b", re.IGNORECASE),
    re.compile(r"\bvâng\b", re.IGNORECASE),
    re.compile(r"\byes\b", re.IGNORECASE),
    re.compile(r"\bcorrect\b", re.IGNORECASE),
    re.compile(r"\bcó\s+thể\b", re.IGNORECASE),
    re.compile(r"\bđược\s+phép\b", re.IGNORECASE),
    re.compile(r"\ballowed\b", re.IGNORECASE),
    re.compile(r"\beligible\b", re.IGNORECASE),
]

_NO_EVIDENCE_ANSWER = "Không tìm thấy đủ bằng chứng trong các tài liệu đã tải lên."


def normalize_evidence(chunks: list[dict]) -> list[EvidenceItem]:
    """Assign stable evidence IDs to retrieved chunks."""
    items: list[EvidenceItem] = []
    for idx, chunk in enumerate(chunks):
        items.append(
            EvidenceItem(
                id=f"E{idx + 1}",
                doc_id=chunk.get("doc_id") or "unknown",
                chunk_id=chunk.get("chunk_id") or f"chunk-{idx}",
                text=str(chunk.get("text") or ""),
                page=chunk.get("page"),
                scene=chunk.get("scene"),
                timestamp=chunk.get("timestamp"),
                score=float(chunk.get("score", 0.0)),
            )
        )
    return items


def format_evidence_for_prompt(evidence: list[EvidenceItem]) -> str:
    """Format evidence items for inclusion in an LLM prompt."""
    parts: list[str] = []
    for item in evidence:
        markers = [f"{item.id}"]
        if item.doc_id:
            markers.append(f"doc_id={item.doc_id}")
        if item.page is not None:
            markers.append(f"page={item.page}")
        if item.scene is not None:
            markers.append(f"scene={item.scene}")
        if item.timestamp is not None:
            markers.append(f"time={item.timestamp}s")
        header = "[" + " | ".join(markers) + "]"
        parts.append(f"{header}\n{item.text}")
    return "\n\n---\n\n".join(parts)


def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _detect_restrictive_evidence(evidence: list[EvidenceItem]) -> list[str]:
    """Return IDs of evidence items containing restrictive eligibility phrases."""
    return [item.id for item in evidence if _matches_any(item.text, _RESTRICTIVE_PATTERNS)]


def _detect_outsider_question(question: str) -> bool:
    """Detect whether the question asks about outsiders or non-members."""
    return _matches_any(question, _OUTSIDER_PATTERNS)


def _answer_looks_affirmative(answer_text: str) -> bool:
    """Detect affirmative wording in an answer text."""
    return _matches_any(answer_text, _AFFIRMATIVE_MARKERS)


def _safe_eligibility_answer(question: str) -> str:
    """Return a cautious answer when evidence restricts participation."""
    if _matches_any(question, _OUTSIDER_EN_PATTERNS):
        return (
            "The document only confirms the restricted group mentioned. "
            "It does not establish that outsiders or non-members can participate."
        )
    return (
        "Tài liệu chỉ xác nhận nhóm đối tượng bị giới hạn được nêu. "
        "Không có bằng chứng cho thấy người ngoài/người không thuộc nhóm này có thể tham gia."
    )


def validate_evidence_ids(
    answer: FaithfulAnswer, evidence: list[EvidenceItem]
) -> tuple[FaithfulAnswer, list[str]]:
    """Remove invalid evidence IDs and downgrade unsupported claims."""
    valid_ids = {item.id for item in evidence}
    cleaned = [eid for eid in answer.evidence_ids if eid in valid_ids]
    guard_warnings: list[str] = []

    invalid_count = len(answer.evidence_ids) - len(cleaned)
    if invalid_count:
        guard_warnings.append(
            f"{invalid_count} cited evidence ID(s) not found in available evidence."
        )

    if not cleaned:
        if answer.polarity != "unknown":
            guard_warnings.append("No valid evidence IDs; polarity downgraded to unknown.")
        return (
            FaithfulAnswer(
                answer=answer.answer,
                polarity="unknown",
                evidence_ids=[],
                warnings=list(answer.warnings) + guard_warnings,
            ),
            guard_warnings,
        )

    return (
        FaithfulAnswer(
            answer=answer.answer,
            polarity=answer.polarity,
            evidence_ids=cleaned,
            warnings=list(answer.warnings) + guard_warnings,
        ),
        guard_warnings,
    )


def apply_eligibility_guard(
    answer: FaithfulAnswer, evidence: list[EvidenceItem], question: str
) -> tuple[FaithfulAnswer, list[str]]:
    """Override affirmative answers that contradict restrictive eligibility evidence."""
    restricted_ids = _detect_restrictive_evidence(evidence)
    if not restricted_ids:
        return answer, []

    if not _detect_outsider_question(question):
        return answer, []

    is_affirmative = answer.polarity == "yes" or _answer_looks_affirmative(answer.answer)
    if not is_affirmative:
        return answer, []

    guard_warning = (
        "Guard detected restrictive eligibility evidence and an outsider-scope question; "
        "affirmative answer is not faithful to the evidence."
    )
    safe_answer = FaithfulAnswer(
        answer=_safe_eligibility_answer(question),
        polarity="no",
        evidence_ids=restricted_ids,
        warnings=list(answer.warnings) + [guard_warning],
    )
    return safe_answer, [guard_warning]


def apply_guard_rules(
    answer: FaithfulAnswer, evidence: list[EvidenceItem], question: str
) -> tuple[FaithfulAnswer, list[str]]:
    """Run validation and deterministic guard rules, returning any warnings."""
    validated, validation_warnings = validate_evidence_ids(answer, evidence)
    guarded, guard_warnings = apply_eligibility_guard(validated, evidence, question)
    all_warnings = validation_warnings + guard_warnings
    return guarded, all_warnings


def _build_safe_fallback(
    evidence: list[EvidenceItem], extra_warnings: list[str], question: str = ""
) -> FaithfulAnswer:
    """Return a conservative fallback when structured generation fails."""
    restricted_ids = _detect_restrictive_evidence(evidence)
    if restricted_ids and _detect_outsider_question(question):
        return FaithfulAnswer(
            answer=_safe_eligibility_answer(question),
            polarity="no",
            evidence_ids=restricted_ids,
            warnings=extra_warnings
            or ["Câu trả lờI không vượt qua kiểm tra faithfulness sau khi thử lạI."],
        )
    return FaithfulAnswer(
        answer=_NO_EVIDENCE_ANSWER,
        polarity="unknown",
        evidence_ids=[item.id for item in evidence],
        warnings=extra_warnings
        or ["Câu trả lờI không vượt qua kiểm tra faithfulness sau khi thử lạI."],
    )


async def generate_faithful_answer(
    question: str,
    evidence: list[EvidenceItem],
    history: str = "",
    max_retries: int = 1,
    is_chat: bool = False,
) -> FaithfulAnswer:
    """Generate a faithfulness-guarded answer for the given evidence.

    The model is asked for a structured answer with evidence IDs. Returned IDs
    are validated and deterministic guard rules are applied. If the model output
    is invalid or contradicts the evidence, one bounded correction retry is made
    before returning a safe fallback answer.
    """
    if not evidence:
        return FaithfulAnswer(
            answer=_NO_EVIDENCE_ANSWER,
            polarity="unknown",
            evidence_ids=[],
            warnings=[],
        )

    context = format_evidence_for_prompt(evidence)
    if is_chat:
        base_prompt = build_faithful_chat_prompt(
            question=question, context=context, history=history
        )
    else:
        base_prompt = build_faithful_answer_prompt(
            question=question, context=context, history=history
        )

    guard_warnings: list[str] = []
    prompt = base_prompt

    for attempt in range(max_retries + 1):
        if attempt > 0 and guard_warnings:
            hint = "\n".join(f"- {w}" for w in guard_warnings)
            prompt = (
                f"{base_prompt}\n\nYour previous response failed faithfulness validation. "
                f"Fix these issues and respond with valid JSON only:\n{hint}"
            )

        try:
            raw = await generate_structured(
                prompt,
                FaithfulAnswer,
                system_prompt=FAITHFUL_ANSWER_SYSTEM,
                max_retries=1,
                use_instructor=False,
            )
        except GenerationError:
            break

        guarded, guard_warnings = apply_guard_rules(raw, evidence, question)
        if not guard_warnings:
            return guarded

    # Fallback: deterministic eligibility guard still applies even without model output.
    return _build_safe_fallback(evidence, guard_warnings, question)


def evidence_item_to_citation(item: EvidenceItem) -> dict:
    """Convert an evidence item to a Citation-shaped dict."""
    from app.models.schemas import Citation

    return Citation(
        doc_id=item.doc_id,
        page=item.page,
        scene=item.scene,
        timestamp=item.timestamp,
        chunk_text=item.text[:500],
    ).model_dump()
