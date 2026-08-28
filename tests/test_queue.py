"""Queue merge, unique titles, and preview status (no Drive / Cairo)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from session_date import strip_session_date
from song_queue import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PREVIEWED,
    STATUS_QUEUED,
    append_unseen,
    audio_path,
    load_queue,
    newest_take_per_title,
    normalize_item,
    save_queue,
    start_or_none,
    status_after_preview,
    style_letter,
    title_from_filename,
)


class TitleFromFilenameTests(unittest.TestCase):
    def test_strips_track_number_and_date(self) -> None:
        self.assertEqual(title_from_filename("07 - Gumbia.mp3"), "Gumbia")
        self.assertEqual(
            title_from_filename("A Funny Handshake May 16 2026.mp3"),
            "A Funny Handshake",
        )
        self.assertEqual(
            title_from_filename("07 - Gumbia May 16 2026.wav"),
            "Gumbia",
        )

    def test_strip_session_date_helper(self) -> None:
        self.assertEqual(strip_session_date("A Funny Handshake May 16 2026"), "A Funny Handshake")
        self.assertEqual(strip_session_date("Whale Song"), "Whale Song")


class NewestTakeTests(unittest.TestCase):
    def test_keeps_latest_created_time_per_title(self) -> None:
        tracks = [
            {
                "title": "Gumbia",
                "file": "07 - Gumbia.mp3",
                "driveId": "old",
                "createdTime": "2026-05-16T00:00:00.000Z",
                "session": "First Time KC May 16 2026",
            },
            {
                "title": "gumbia",
                "file": "Gumbia.wav",
                "driveId": "new",
                "createdTime": "2026-07-11T00:00:00.000Z",
                "session": "July 11 2026",
            },
            {
                "title": "Whale Song",
                "file": "04 - Whale Song.wav",
                "driveId": "whale",
                "createdTime": "2026-05-16T00:00:00.000Z",
                "session": "First Time KC May 16 2026",
            },
        ]
        takes = newest_take_per_title(tracks)
        by_title = {t["title"].casefold(): t for t in takes}
        self.assertEqual(len(takes), 2)
        self.assertEqual(by_title["gumbia"]["driveId"], "new")
        self.assertEqual(by_title["whale song"]["driveId"], "whale")


class AppendUnseenTests(unittest.TestCase):
    def test_appends_without_reshuffling(self) -> None:
        existing = [
            normalize_item(
                {"title": "Gumbia", "file": "g.mp3", "driveId": "g1", "status": "previewed"},
                0,
            )
        ]
        takes = [
            {"title": "Gumbia", "file": "g2.mp3", "driveId": "g2", "session": "July 11 2026"},
            {"title": "Whale Song", "file": "w.wav", "driveId": "w1", "session": "May 16 2026", "date": "May 16, 2026"},
        ]
        items, added = append_unseen(existing, takes)
        self.assertEqual(added, 1)
        self.assertEqual([it["title"] for it in items], ["Gumbia", "Whale Song"])
        self.assertEqual(items[0]["status"], "previewed")
        self.assertEqual(items[0]["driveId"], "g1")
        self.assertEqual(items[1]["status"], STATUS_QUEUED)
        self.assertEqual(items[1]["position"], 1)

    def test_skips_existing_drive_id(self) -> None:
        existing = [normalize_item({"title": "Other", "file": "o.mp3", "driveId": "same"}, 0)]
        takes = [{"title": "Brand New", "file": "n.mp3", "driveId": "same"}]
        items, added = append_unseen(existing, takes)
        self.assertEqual(added, 0)
        self.assertEqual(len(items), 1)


class StatusTests(unittest.TestCase):
    def test_preview_does_not_mark_done(self) -> None:
        self.assertEqual(status_after_preview(STATUS_QUEUED), STATUS_PREVIEWED)
        self.assertEqual(status_after_preview(STATUS_FAILED), STATUS_PREVIEWED)
        self.assertEqual(status_after_preview(STATUS_PREVIEWED), STATUS_PREVIEWED)
        self.assertEqual(status_after_preview(STATUS_DONE), STATUS_DONE)
        self.assertNotEqual(status_after_preview(STATUS_QUEUED), STATUS_DONE)


class SidebarValueTests(unittest.TestCase):
    def test_style_letter_normalizes_toggle_labels(self) -> None:
        self.assertEqual(style_letter("A"), "a")
        self.assertEqual(style_letter("b"), "b")
        self.assertEqual(style_letter("nope", "c"), "c")

    def test_zero_or_empty_start_means_seeded_window(self) -> None:
        self.assertIsNone(start_or_none(None))
        self.assertIsNone(start_or_none(""))
        self.assertIsNone(start_or_none(0))
        self.assertIsNone(start_or_none(0.0))
        self.assertEqual(start_or_none(12.5), 12.5)
        self.assertEqual(start_or_none("30"), 30.0)


class QueueFileTests(unittest.TestCase):
    def test_round_trip_and_legacy_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "queue.json")
            items = [
                normalize_item(
                    {
                        "title": "Gumbia",
                        "file": "07 - Gumbia.mp3",
                        "session": "First Time KC May 16 2026",
                        "driveId": "abc",
                        "style": "b",
                        "aspect": "square",
                        "seed": 99,
                        "date": "May 16, 2026",
                        "start": 12.5,
                        "duration": 60,
                    },
                    0,
                )
            ]
            save_queue({"items": items}, path)
            loaded = load_queue(path)
            self.assertEqual(loaded["items"][0]["title"], "Gumbia")
            self.assertEqual(loaded["items"][0]["style"], "b")
            self.assertEqual(loaded["items"][0]["start"], 12.5)
            self.assertEqual(audio_path(loaded["items"][0]), "audio/First Time KC May 16 2026/07 - Gumbia.mp3")

            legacy = Path(tmp) / "instagram-queue.json"
            legacy.write_text(json.dumps([{"title": "Whale Song", "file": "w.wav", "driveId": "w"}]), encoding="utf-8")
            from_legacy = load_queue(str(legacy))
            self.assertEqual(from_legacy["items"][0]["title"], "Whale Song")


if __name__ == "__main__":
    unittest.main()
