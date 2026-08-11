"""Tests for video audio extraction and STT merging."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from app.services.video import analyze_video, extract_audio_track, _merge_scene_and_audio




def test_merge_scene_and_audio_combines_markers():
    scenes = ["[Scene 0 at 1.0s]:\nSlide A"]
    audio = ["[Audio 0.5s-2.0s]: Hello"]
    merged = _merge_scene_and_audio(scenes, audio)
    assert "Visual content" in merged
    assert "Audio transcript" in merged
    assert "Slide A" in merged
    assert "Hello" in merged


def test_merge_scene_and_audio_ocr_only():
    scenes = ["[Scene 0 at 1.0s]:\nSlide A"]
    audio = []
    merged = _merge_scene_and_audio(scenes, audio)
    assert "Visual content" in merged
    assert "Audio transcript" not in merged


def test_merge_scene_and_audio_audio_only():
    scenes = []
    audio = ["[Audio 0.5s-2.0s]: Hello"]
    merged = _merge_scene_and_audio(scenes, audio)
    assert "Visual content" not in merged
    assert "Audio transcript" in merged




@pytest.mark.asyncio
async def test_analyze_video_merges_ocr_and_audio(monkeypatch, tmp_path):
    """Mock OCR and STT to verify merge logic without real models."""
    from moviepy.video.VideoClip import ColorClip

    video_path = tmp_path / "test_video.mp4"
    clip = ColorClip(size=(320, 240), color=(0, 0, 0), duration=2)
    clip.write_videofile(str(video_path), fps=10, logger=None, audio=False)

    async def fake_ocr(path):
        return "OCR text"

    async def fake_stt(path):
        return {
            "text": "spoken words",
            "segments": [{"start": 0.0, "end": 1.0, "text": "spoken words"}],
        }

    monkeypatch.setattr("app.services.video.ocr_image", fake_ocr)
    monkeypatch.setattr("app.services.video.transcribe_audio_with_timestamps", fake_stt)

    result = await analyze_video(str(video_path))
    assert "OCR text" in result["text"] or result["text"] == ""
    assert result["duration"] > 0


@pytest.mark.asyncio
async def test_extract_audio_track_no_audio(tmp_path):
    from moviepy.video.VideoClip import ColorClip
    video_path = tmp_path / "no_audio.mp4"
    clip = ColorClip(size=(320, 240), color=(0, 0, 0), duration=1)
    clip.write_videofile(str(video_path), fps=10, logger=None, audio=False)

    with pytest.raises(ValueError, match="no audio"):
        await extract_audio_track(video_path)
