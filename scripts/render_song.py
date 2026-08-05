#!/usr/bin/env python3
"""Render one Shorts MP4 for a song + layout style.

Examples:
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a
  .venv/bin/python3 scripts/render_song.py audio/02\\ -\\ Little\\ E.wav b
  .venv/bin/python3 scripts/render_song.py "07 - Gumbia.wav" classic
"""

from __future__ import annotations

import os
import sys

# Allow running from repo root or scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from art.stills import seed_from_song
from render import LAYOUT_STYLES, RenderOptions, render

ALIASES = {"a": "a", "b": "b", "classic": "classic", "c": "classic"}


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: scripts/render_song.py <audio-file> <a|b|classic>\n"
            'Example: .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a'
        )

    song_arg = sys.argv[1]
    style_key = sys.argv[2].strip().lower()
    layout_style = ALIASES.get(style_key, style_key)
    if layout_style not in LAYOUT_STYLES:
        raise SystemExit(f"Unknown style {sys.argv[2]!r}; use a, b, or classic")

    song_path = song_arg if os.path.isabs(song_arg) else song_arg
    if not os.path.isfile(song_path):
        candidate = os.path.join("audio", os.path.basename(song_arg))
        if os.path.isfile(candidate):
            song_path = candidate
        else:
            raise SystemExit(f"Audio not found: {song_arg}")

    song_name = os.path.splitext(os.path.basename(song_path))[0]
    seed = seed_from_song(song_name)
    print(f"Song: {song_name}")
    print(f"Layout: {layout_style}")
    print(f"Seed: {seed}")

    out = render(
        song_path,
        song_name,
        RenderOptions(master_seed=seed, layout_style=layout_style),
    )
    print(f"\nDone — {out}")


if __name__ == "__main__":
    main()
