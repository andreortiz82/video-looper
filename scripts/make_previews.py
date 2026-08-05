#!/usr/bin/env python3
"""Write static Style A/B preview PNGs for a song (3 backgrounds each).

Examples:
  .venv/bin/python3 scripts/make_previews.py "04 - Whale Song.wav"
  .venv/bin/python3 scripts/make_previews.py "08 - Space Cowboy.wav"
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from art.stills import seed_from_song
from render import write_layout_previews


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: scripts/make_previews.py <audio-file>\n"
            'Example: .venv/bin/python3 scripts/make_previews.py "04 - Whale Song.wav"'
        )

    song_arg = sys.argv[1]
    song_path = song_arg
    if not os.path.isfile(song_path):
        candidate = os.path.join("audio", os.path.basename(song_arg))
        if os.path.isfile(candidate):
            song_path = candidate
        else:
            raise SystemExit(f"Audio not found: {song_arg}")

    song_name = os.path.splitext(os.path.basename(song_path))[0]
    seed = seed_from_song(song_name)
    print(f"Song: {song_name} | seed={seed}")
    paths = write_layout_previews(song_path, song_name, master_seed=seed)
    print(f"\nWrote {len(paths)} previews:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
