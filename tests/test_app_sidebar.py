"""Sidebar wireframe labels and order (source-level, no Streamlit runtime)."""

from __future__ import annotations

import unittest
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class SidebarWireframeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = APP_PATH.read_text(encoding="utf-8")

    def test_five_groups_in_order(self) -> None:
        labels = [
            "Data source",
            "Song details",
            "Visual settings and preview",
            "Timing",
            "Final actions",
        ]
        positions = [self.src.index(f'"{name}"') for name in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertGreaterEqual(self.src.count("st.divider()"), 4)

    def test_control_labels_in_order(self) -> None:
        labels = [
            "Scan Google Drive",
            "Choose Song",
            "Display Name",
            "Display Date",
            "Style",
            "Aspect Ratio",
            "Art Seed",
            "ROLL",
            "Render Preview Stills",
            "Start (seconds)",
            "Duration (seconds)",
            "Render Video",
            "Mark Done",
        ]
        last = -1
        for label in labels:
            idx = self.src.index(f'"{label}"')
            self.assertGreater(idx, last, f"{label} out of order")
            last = idx

    def test_main_pane_has_no_duplicate_song_picker(self) -> None:
        self.assertNotIn("Selected song", self.src)
        self.assertEqual(self.src.count("Choose Song"), 1)

    def test_dropped_sidebar_checkboxes(self) -> None:
        self.assertNotIn("Set in-point", self.src)
        self.assertNotIn("Set clip seed", self.src)
        self.assertNotIn("Mark done if MP4 render succeeds", self.src)
        self.assertNotIn("Reroll", self.src)
        self.assertNotIn('"Render MP4"', self.src)

    def test_preview_never_assigns_done(self) -> None:
        self.assertIn("status_after_preview", self.src)
        preview_handler = self.src[
            self.src.index("if preview_clicked:") : self.src.index("if render_clicked:")
        ]
        self.assertIn("status_after_preview", preview_handler)
        self.assertNotIn("STATUS_DONE", preview_handler)


if __name__ == "__main__":
    unittest.main()
