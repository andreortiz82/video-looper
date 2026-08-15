"""Optional video frame sampling synced to the audio clip window."""

from __future__ import annotations

import os

from moviepy import VideoFileClip
from PIL import Image

VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")


def resolve_video_path(path: str | None) -> str | None:
    if not path:
        return None
    if os.path.isfile(path):
        return path
    # Allow basename under video/
    candidate = os.path.join("video", os.path.basename(path))
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(f"Video not found: {path}")


def list_videos(video_dir: str = "video") -> list[str]:
    if not os.path.isdir(video_dir):
        return []
    return sorted(
        f
        for f in os.listdir(video_dir)
        if f.lower().endswith(VIDEO_EXTENSIONS) and not f.startswith(".")
    )


def sample_video_frames(
    video_path: str,
    *,
    times: list[float],
    video_start: float = 0.0,
) -> list[Image.Image]:
    """Grab RGB frames at ``video_start + t`` for each relative time ``t``.

    ``times`` are offsets within the audio window (same clock as render motion).
    Frames clamp to the last available frame if the video is shorter.
    """
    if not times:
        return []

    clip = VideoFileClip(video_path)
    try:
        duration = float(clip.duration or 0.0)
        if duration <= 0:
            raise ValueError(f"Video has no duration: {video_path}")

        frames: list[Image.Image] = []
        for t in times:
            abs_t = video_start + float(t)
            # Loop short videos across the audio window
            if abs_t >= duration:
                abs_t = abs_t % duration
            abs_t = min(max(0.0, abs_t), max(0.0, duration - 1e-3))
            arr = clip.get_frame(abs_t)
            frames.append(Image.fromarray(arr.astype("uint8")).convert("RGB"))
        return frames
    finally:
        clip.close()


def sample_even_video_frames(
    video_path: str,
    *,
    count: int,
    window_duration: float,
    video_start: float = 0.0,
) -> list[Image.Image]:
    """Sample ``count`` frames evenly across ``[0, window_duration)``."""
    if count <= 0:
        return []
    if count == 1:
        times = [0.0]
    else:
        step = window_duration / count
        times = [step * i + step * 0.5 for i in range(count)]
    return sample_video_frames(video_path, times=times, video_start=video_start)
