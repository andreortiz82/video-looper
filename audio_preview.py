"""Duration-locked audio clip for the Streamlit GUI player.

Playback start 0 is the beginning of the file (not the seeded random window
used by render when start is empty/0). Clips are cached under
``output/audio-preview/``.
"""

from __future__ import annotations

import os
from typing import Any

AUDIO_PREVIEW_DIR = os.path.join("output", "audio-preview")
DEFAULT_DURATION = 60.0


def playback_start(value: Any) -> float:
    """In-point for the player. 0 means the start of the file."""
    if value is None or value == "":
        return 0.0
    try:
        start = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, start)


def playback_duration(value: Any) -> float:
    if value is None or value == "":
        return DEFAULT_DURATION
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DURATION
    return duration if duration > 0 else DEFAULT_DURATION


def preview_cache_path(
    *,
    drive_id: str = "",
    stem: str = "",
    start: float,
    duration: float,
) -> str:
    ident = _safe_token(drive_id or stem or "song")
    start_tag = f"{float(start):.3f}".replace(".", "p")
    dur_tag = f"{float(duration):.3f}".replace(".", "p")
    return os.path.join(AUDIO_PREVIEW_DIR, f"{ident}_{start_tag}s_{dur_tag}s.mp3")


def write_preview_clip(song_path: str, dest: str, start: float, duration: float) -> str:
    """Slice ``[start, start+duration]`` to ``dest``. Reuse dest when present."""
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return dest
    from moviepy import AudioFileClip

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    clip = AudioFileClip(song_path)
    sliced = None
    tmp = f"{dest}.part.mp3"
    try:
        song_dur = float(clip.duration or 0.0)
        if song_dur <= 0:
            raise ValueError(f"Audio has no duration: {song_path}")
        clip_dur = min(float(duration), song_dur)
        if clip_dur <= 0:
            raise ValueError(f"duration must be > 0 (got {duration})")
        max_start = max(0.0, song_dur - clip_dur)
        window_start = min(max(0.0, float(start)), max_start)
        sliced = clip.subclipped(window_start, window_start + clip_dur)
        sliced.write_audiofile(tmp, logger=None)
        os.replace(tmp, dest)
        return dest
    finally:
        if sliced is not None:
            sliced.close()
        clip.close()
        if os.path.isfile(tmp):
            os.remove(tmp)


def _safe_token(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in (value or ""))
    cleaned = cleaned.strip("_")[:48]
    return cleaned or "song"
