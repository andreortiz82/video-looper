"""Duration-locked GUI audio clips (MoviePy slice + cache)."""

from __future__ import annotations

import os
import subprocess
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


def _probe_clip(path: str) -> tuple[float, float, float]:
    """Return (duration, full RMS, first-0.4s RMS) via ffmpeg.

    MoviePy's mp3 reader can report silence on short clips; the files themselves
    are fine for HTML5 / ``st.audio``.
    """
    wav_path = f"{path}.check.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", wav_path],
        check=True,
        capture_output=True,
    )
    try:
        with wave.open(wav_path) as wav:
            rate = wav.getframerate()
            nch = wav.getnchannels()
            n = wav.getnframes()
            data = np.frombuffer(wav.readframes(n), dtype=np.int16).astype(np.float64)
            if nch > 1:
                data = data.reshape(-1, nch).mean(axis=1)
            data /= 32768.0
        duration = n / rate if rate else 0.0
        full = float(np.sqrt(np.mean(data**2))) if len(data) else 0.0
        head = data[: max(1, int(0.4 * rate))]
        head_rms = float(np.sqrt(np.mean(head**2))) if len(head) else 0.0
        return duration, full, head_rms
    finally:
        if os.path.isfile(wav_path):
            os.remove(wav_path)


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
            loud_dur, loud_rms, _ = _probe_clip(loud)
            self.assertAlmostEqual(loud_dur, 1.0, delta=0.15)
            self.assertGreater(loud_rms, 0.1)

            quiet = str(Path(tmp) / "start0_dur1.mp3")
            write_preview_clip(src, quiet, start=0.0, duration=1.0)
            quiet_dur, quiet_rms, _ = _probe_clip(quiet)
            self.assertAlmostEqual(quiet_dur, 1.0, delta=0.15)
            self.assertLess(quiet_rms, loud_rms / 4)

            sixty = str(Path(tmp) / "start12_dur60.mp3")
            write_preview_clip(src, sixty, start=12.0, duration=60.0)
            sixty_dur, _, _ = _probe_clip(sixty)
            # Source is only 3s; clamp rather than invent audio.
            self.assertAlmostEqual(sixty_dur, 3.0, delta=0.2)

    def test_start_12_duration_60_yields_sixty_second_clip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = str(Path(tmp) / "long.wav")
            _write_segmented_wav(src, [(12.0, 0.0), (63.0, 0.4)])
            dest = str(Path(tmp) / "clip.mp3")
            write_preview_clip(src, dest, start=12.0, duration=60.0)
            dur, rms, head_rms = _probe_clip(dest)
            self.assertAlmostEqual(dur, 60.0, delta=0.35)
            self.assertGreater(rms, 0.08)
            self.assertGreater(head_rms, 0.08)

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
