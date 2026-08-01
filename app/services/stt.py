"""Speech-to-text via faster-whisper."""
from faster_whisper import WhisperModel
from app.config import settings

_model: WhisperModel | None = None


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

    text = _extract_text(segments)

    return {
        "text": text,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
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
        result_segments.append(
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            }
        )

    full_text = " ".join(s["text"] for s in result_segments)

    return {
        "text": full_text,
        "language": info.language,
        "duration": info.duration,
        "segments": result_segments,
    }
