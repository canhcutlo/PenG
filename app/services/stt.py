"""Speech-to-text via faster-whisper."""
import re

from faster_whisper import WhisperModel
from app.config import settings

_model: WhisperModel | None = None

# Common Whisper hallucination/noise markers (conservative removal only).
_NOISE_MARKERS = re.compile(
    r"\[(?:BLANK_AUDIO|NO_SPEECH|SILENCE|MUSIC|MÚSICA|MUSIQUE|SFX)\]|"
    r"\((?:nhạc|music|noise|silence)\)",
    re.IGNORECASE,
)

# Collapse a word or short phrase repeated more than 3 times consecutively.
_REPEATED_TOKENS = re.compile(r"(\b\w+(?:\s+\w+)?\b)(?:\s+\1){3,}", re.IGNORECASE)


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        device = "cpu" if settings.llm_device not in ("cuda", "cpu") else settings.llm_device
        compute_type = "float16" if device == "cuda" else "int8"
        _model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
        )
    return _model


def _clean_segment_text(text: str) -> str:
    """Conservatively clean obvious Whisper artifacts without changing content."""
    text = _NOISE_MARKERS.sub("", text)
    text = _REPEATED_TOKENS.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_text(segments) -> str:
    return " ".join(seg.text for seg in segments).strip()


async def transcribe_audio(file_path: str) -> dict:
    """Transcribe audio file. Returns dict with text, language, segments."""
    model = get_model()
    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        word_timestamps=False,
        condition_on_previous_text=True,
    )

    result_segments = []
    for seg in segments:
        cleaned = _clean_segment_text(seg.text)
        if cleaned:
            result_segments.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": cleaned,
                }
            )

    text = " ".join(s["text"] for s in result_segments)

    return {
        "text": text,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": result_segments,
    }


async def transcribe_audio_with_timestamps(file_path: str) -> dict:
    """Transcribe audio with segment timestamps."""
    model = get_model()
    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        word_timestamps=True,
    )

    result_segments = []
    for seg in segments:
        cleaned = _clean_segment_text(seg.text)
        if cleaned:
            result_segments.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": cleaned,
                }
            )

    full_text = " ".join(s["text"] for s in result_segments)

    return {
        "text": full_text,
        "language": info.language,
        "duration": info.duration,
        "segments": result_segments,
    }
