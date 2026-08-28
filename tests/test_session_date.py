"""Chrome date comes from the session folder / filename, not render time."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from session_date import format_song_date, parse_session_date


FOLDER_CASES = (
    ("First Time KC May 16 2026", "May 16, 2026"),
    ("July 11 2026", "Jul 11, 2026"),
    ("Jan15 2026 DrumAndBassOnly", "Jan 15, 2026"),
    ("May 24th 26 St. Charles Place", "May 24, 2026"),
    ("Feb 7th 2026", "Feb 7, 2026"),
    ("Jun 7 2026", "Jun 7, 2026"),
    ("April 9 2026", "Apr 9, 2026"),
    ("Mar 31 2026", "Mar 31, 2026"),
    ("Aug 8 2026", "Aug 8, 2026"),
)


class ParseSessionDateTests(unittest.TestCase):
    def test_folder_name_patterns(self) -> None:
        for name, expected in FOLDER_CASES:
            with self.subTest(name=name):
                parsed = parse_session_date(name)
                self.assertIsNotNone(parsed, name)
                self.assertEqual(format_song_date(override=name), expected)

    def test_filename_with_extension(self) -> None:
        parsed = parse_session_date("A Funny Handshake May 16 2026.mp3")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual((parsed.year, parsed.month, parsed.day), (2026, 5, 16))

    def test_no_date_returns_none(self) -> None:
        self.assertIsNone(parse_session_date("audio"))
        self.assertIsNone(parse_session_date("Whale Song"))
        self.assertIsNone(parse_session_date(""))


class FormatSongDateTests(unittest.TestCase):
    def test_parent_folder_wins_over_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "First Time KC May 16 2026"
            folder.mkdir()
            song = folder / "A Funny Handshake May 16 2026.mp3"
            song.write_bytes(b"")
            os.utime(song, (datetime.now().timestamp(), datetime.now().timestamp()))
            self.assertEqual(format_song_date(str(song)), "May 16, 2026")

    def test_nested_audio_session_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "audio" / "First Time KC May 16 2026"
            folder.mkdir(parents=True)
            song = folder / "track.mp3"
            song.write_bytes(b"")
            self.assertEqual(format_song_date(str(song)), "May 16, 2026")

    def test_filename_when_parent_has_no_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "audio"
            folder.mkdir()
            song = folder / "A Funny Handshake May 16 2026.mp3"
            song.write_bytes(b"")
            self.assertEqual(format_song_date(str(song)), "May 16, 2026")

    def test_parent_wins_over_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "July 11 2026"
            folder.mkdir()
            song = folder / "A Funny Handshake May 16 2026.mp3"
            song.write_bytes(b"")
            self.assertEqual(format_song_date(str(song)), "Jul 11, 2026")

    def test_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "July 11 2026"
            folder.mkdir()
            song = folder / "song.mp3"
            song.write_bytes(b"")
            self.assertEqual(format_song_date(str(song), "May 16, 2026"), "May 16, 2026")
            self.assertEqual(format_song_date(str(song), "May 16 2026"), "May 16, 2026")

    def test_override_without_file(self) -> None:
        self.assertEqual(format_song_date(None, "May 16, 2026"), "May 16, 2026")

    def test_path_parses_even_if_file_missing(self) -> None:
        path = os.path.join(
            "audio",
            "First Time KC May 16 2026",
            "A Funny Handshake May 16 2026.mp3",
        )
        self.assertEqual(format_song_date(path), "May 16, 2026")

    def test_mtime_last_resort_not_today(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "Whale Song.wav"
            song.write_bytes(b"")
            past = datetime(2020, 1, 15, 12, 0, 0)
            os.utime(song, (past.timestamp(), past.timestamp()))
            self.assertEqual(format_song_date(str(song)), "Jan 15, 2020")
            self.assertNotEqual(format_song_date(str(song)), format_song_date())

    def test_missing_file_without_date_uses_now(self) -> None:
        # No path date and no file → render-time fallback is allowed.
        today = format_song_date()
        self.assertRegex(today, r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")


class CliWiringTests(unittest.TestCase):
    def test_render_song_wires_date_override(self) -> None:
        src = Path("scripts/render_song.py").read_text(encoding="utf-8")
        self.assertIn('"--date"', src)
        self.assertIn("song_date=args.song_date", src)
        self.assertIn("dest=\"song_date\"", src)


if __name__ == "__main__":
    unittest.main()
