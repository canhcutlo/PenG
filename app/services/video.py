"""Video analysis: scene detection + keyframe OCR."""
import os
import tempfile
from pathlib import Path
from moviepy import VideoFileClip
from scenedetect import detect, AdaptiveDetector
from scenedetect import FrameTimecode
from app.services.ocr import ocr_image
from app.config import settings

MAX_KEYFRAMES = 20  # safety cap for long videos


async def analyze_video(video_path: str) -> dict:
    """
    Detect scenes in a video and OCR the first frame of each scene.
    Returns dict with text, scene metadata, and optional audio path.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    scene_list = detect(str(video_path), AdaptiveDetector())

    # Extract keyframes
    keyframe_dir = settings.upload_dir / "keyframes" / video_path.stem
    keyframe_dir.mkdir(parents=True, exist_ok=True)

    clip = VideoFileClip(str(video_path))
    duration = clip.duration

    # If no scenes detected, sample evenly
    if not scene_list:
        sample_count = min(5, max(1, int(duration / 10)))
        scene_list = _sample_timecodes(clip, sample_count)

    scenes = []
    texts = []
    for i, (start_tc, end_tc) in enumerate(scene_list[:MAX_KEYFRAMES]):
        start_sec = float(start_tc.get_seconds())
        end_sec = float(end_tc.get_seconds())
        frame_path = keyframe_dir / f"scene_{i:04d}.png"
        clip.save_frame(str(frame_path), t=start_sec)
        frame_text = await ocr_image(str(frame_path))
        os.remove(str(frame_path))

        if frame_text.strip():
            texts.append(f"[Scene {i} at {start_sec:.1f}s]:\n{frame_text}")

        scenes.append(
            {
                "scene_index": i,
                "start": start_sec,
                "end": end_sec,
            }
        )

    clip.close()

    # Cleanup empty dir
    try:
        keyframe_dir.rmdir()
    except OSError:
        pass

    return {
        "text": "\n\n".join(texts),
        "scenes": scenes,
        "duration": duration,
    }


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
