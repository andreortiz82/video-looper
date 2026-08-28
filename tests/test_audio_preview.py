"""Duration-locked GUI audio clips (MoviePy slice + cache)."""

from __future__ import annotations

import math
import os
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_preview import (
    playback_duration,
    playback_start,
    preview_cache_path,
    write_preview_clip,
)
from song_queue import start_or_none


def _write_segmented_wav(path: str, segments: list[tuple[float, float]], rate: int = 22050) -> None:
    """Write sequential (seconds, amplitude) blocks of a sine (or silence if amp=0)."""
    chunks: list[np.ndarray] = []
    freq = 440.0
    sample_i = 0
    for seconds, amp in segments:
        n = int(round(seconds * rate))
        t = (np.arange(n) + sample_i) / rate
        samples = (amp * np.sin(2 * np.pi * freq * t) * 32767.0).astype(np.int16)
        chunks.append(samples)
        sample_i += n
    frames = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    with wave.open(path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames.tobytes())


def _mono_samples(path: str) -> tuple[list[float], float]:
    from moviepy import AudioFileClip

    clip = AudioFileClip(path)
    try:
        duration = float(clip.duration or 0.0)
        arr = clip.to_soundarray(fps=22050)
    finally:
        clip.close()
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return arr.tolist(), duration


def _rms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class PlaybackWindowTests(unittest.TestCase):
    def test_zero_start_is_beginning_not_seeded_window(self) -> None:
        self.assertEqual(playback_start(0), 0.0)
        self.assertEqual(playback_start(0.0), 0.0)
        self.assertEqual(playback_start(None), 0.0)
        self.assertEqual(playback_start(""), 0.0)
        self.assertIsNone(start_or_none(0))
        self.assertIsNone(start_or_none(0.0))

    def test_explicit_start_and_default_duration(self) -> None:
        self.assertEqual(playback_start(12), 12.0)
        self.assertEqual(playback_duration(60), 60.0)
        self.assertEqual(playback_duration(None), 60.0)
        self.assertEqual(playback_duration(0), 60.0)


class CachePathTests(unittest.TestCase):
    def test_keyed_by_drive_id_start_and_duration(self) -> None:
        a = preview_cache_path(drive_id="abc123", start=12, duration=60)
        b = preview_cache_path(drive_id="abc123", start=12.0, duration=60.0)
        c = preview_cache_path(drive_id="abc123", start=0, duration=60)
        d = preview_cache_path(drive_id="other", start=12, duration=60)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertTrue(a.endswith(".mp3"))
        self.assertIn("12p000s", a)
        self.assertIn("60p000s", a)


class WritePreviewClipTests(unittest.TestCase):
    def test_slice_matches_start_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = str(Path(tmp) / "song.wav")
            # 1s quiet, 1s loud, 1s quiet — like start=12 / duration=60 on a longer track.
            _write_segmented_wav(src, [(1.0, 0.0), (1.0, 0.5), (1.0, 0.0)])

            loud = str(Path(tmp) / "start1_dur1.mp3")
            write_preview_clip(src, loud, start=1.0, duration=1.0)
            loud_samples, loud_dur = _mono_samples(loud)
            self.assertAlmostEqual(loud_dur, 1.0, delta=0.15)
            self.assertGreater(_rms(loud_samples), 0.1)

            quiet = str(Path(tmp) / "start0_dur1.mp3")
            write_preview_clip(src, quiet, start=0.0, duration=1.0)
            quiet_samples, quiet_dur = _mono_samples(quiet)
            self.assertAlmostEqual(quiet_dur, 1.0, delta=0.15)
            self.assertLess(_rms(quiet_samples), _rms(loud_samples) / 4)

            sixty = str(Path(tmp) / "start12_dur60.mp3")
            write_preview_clip(src, sixty, start=12.0, duration=60.0)
            _, sixty_dur = _mono_samples(sixty)
            # Source is only 3s; clamp rather than invent audio.
            self.assertAlmostEqual(sixty_dur, 3.0, delta=0.2)

    def test_start_12_duration_60_yields_sixty_second_clip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = str(Path(tmp) / "long.wav")
            _write_segmented_wav(src, [(12.0, 0.0), (63.0, 0.4)])
            dest = str(Path(tmp) / "clip.mp3")
            write_preview_clip(src, dest, start=12.0, duration=60.0)
            samples, dur = _mono_samples(dest)
            self.assertAlmostEqual(dur, 60.0, delta=0.35)
            self.assertGreater(_rms(samples), 0.08)
            head = samples[: int(0.4 * 22050)]
            self.assertGreater(_rms(head), 0.08)

    def test_cache_hit_skips_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = str(Path(tmp) / "song.wav")
            dest = str(Path(tmp) / "clip.mp3")
            _write_segmented_wav(src, [(0.4, 0.4)])
            write_preview_clip(src, dest, start=0.0, duration=0.4)
            mtime = os.path.getmtime(dest)
            write_preview_clip(src, dest, start=0.0, duration=0.4)
            self.assertEqual(os.path.getmtime(dest), mtime)


if __name__ == "__main__":
    unittest.main()
