"""Video analysis: scene detection + keyframe OCR + audio STT."""
import os
import shutil
import tempfile
from pathlib import Path
from moviepy import VideoFileClip
from scenedetect import detect, AdaptiveDetector
from scenedetect import FrameTimecode
from app.services.ocr import ocr_image
from app.services.stt import transcribe_audio_with_timestamps
from app.config import settings

MAX_KEYFRAMES = 20


async def analyze_video(video_path: str) -> dict:
    """
    Detect scenes in a video, OCR the first frame of each scene, and transcribe audio.
    Returns dict with merged text, scene metadata, segments, and duration.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    scene_list = detect(str(video_path), AdaptiveDetector())

    keyframe_dir = settings.upload_dir / "keyframes" / video_path.stem
    keyframe_dir.mkdir(parents=True, exist_ok=True)

    clip = VideoFileClip(str(video_path))
    duration = clip.duration

    if not scene_list:
        sample_count = min(5, max(1, int(duration / 10)))
        scene_list = _sample_timecodes(clip, sample_count)

    scenes = []
    scene_texts = []
    for i, (start_tc, end_tc) in enumerate(scene_list[:MAX_KEYFRAMES]):
        start_sec = float(start_tc.seconds)
        end_sec = float(end_tc.seconds)
        frame_path = keyframe_dir / f"scene_{i:04d}.png"
        clip.save_frame(str(frame_path), t=start_sec)
        frame_text = await ocr_image(str(frame_path))
        os.remove(str(frame_path))

        if frame_text.strip():
            scene_texts.append(f"[Scene {i} at {start_sec:.1f}s]:\n{frame_text}")

        scenes.append(
            {
                "scene_index": i,
                "start": start_sec,
                "end": end_sec,
            }
        )

    clip.close()

    try:
        keyframe_dir.rmdir()
    except OSError:
        pass

    audio_texts = []
    audio_segments = []
    audio_path = None
    try:
        audio_path = await extract_audio_track(video_path)
        stt_result = await transcribe_audio_with_timestamps(str(audio_path))
        audio_segments = stt_result.get("segments", [])
        for seg in audio_segments:
            audio_texts.append(f"[Audio {seg['start']:.1f}s-{seg['end']:.1f}s]: {seg['text']}")
    except Exception:
        pass
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                audio_dir = Path(audio_path).parent
                if audio_dir.exists():
                    audio_dir.rmdir()
            except OSError:
                pass

    merged = _merge_scene_and_audio(scene_texts, audio_texts)

    return {
        "text": merged,
        "scenes": scenes,
        "audio_segments": audio_segments,
        "duration": duration,
    }


def _merge_scene_and_audio(scene_texts: list[str], audio_texts: list[str]) -> str:
    """Combine scene OCR and audio transcript into one structured text."""
    parts = []
    if scene_texts:
        parts.append("## Visual content\n\n" + "\n\n".join(scene_texts))
    if audio_texts:
        parts.append("## Audio transcript\n\n" + "\n\n".join(audio_texts))
    return "\n\n".join(parts)


def _sample_timecodes(clip, count: int) -> list:
    """Generate evenly spaced scene timecodes when no scene transitions detected."""
    duration = clip.duration
    if duration <= 0:
        return []
    fps = getattr(clip, "fps", 25.0) or 25.0
    step = duration / (count + 1)
    scenes = []
    for i in range(count):
        start = step * (i + 1)
        end = min(start + 1.0, duration)
        scenes.append(
            (
                FrameTimecode(timecode=start, fps=fps),
                FrameTimecode(timecode=end, fps=fps),
            )
        )
    return scenes


async def extract_audio_track(video_path: str, output_dir: Path | None = None) -> Path:
    """Extract audio from video to WAV. Returns audio path."""
    video_path = Path(video_path)
    if output_dir is None:
        output_dir = settings.upload_dir / "audio" / video_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{video_path.stem}.wav"

    clip = VideoFileClip(str(video_path))
    if clip.audio is None:
        clip.close()
        raise ValueError("Video has no audio track")

    clip.audio.write_audiofile(str(audio_path), fps=16000, logger=None)
    clip.close()
    return audio_path
