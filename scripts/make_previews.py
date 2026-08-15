#!/usr/bin/env python3
"""Write static Style A / B / C preview PNGs for a song (3 variants each).

Examples:
  .venv/bin/python3 scripts/make_previews.py "04 - Whale Song.wav"
  .venv/bin/python3 scripts/make_previews.py "Big E.mp3" --style a --seed 42
  .venv/bin/python3 scripts/make_previews.py "08 - Space Cowboy.wav" --aspect square
  .venv/bin/python3 scripts/make_previews.py "08 - Space Cowboy.wav" --aspect landscape --video clip.mp4
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from art.stills import seed_from_song
from layout import normalize_aspect
from render import LAYOUT_STYLES, write_layout_previews
from video_source import resolve_video_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write Style A/B/C preview PNGs.")
    parser.add_argument("audio_file", help="Path or basename under audio/")
    parser.add_argument(
        "--aspect",
        default="portrait",
        help="portrait|square|landscape (or 9:16|1:1|16:9). Default: portrait",
    )
    parser.add_argument(
        "--style",
        default=None,
        metavar="ABC",
        help="Subset of styles: a, b, c, or comma-separated (default: all)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Art/cover seed override (default: from song filename)",
    )
    parser.add_argument(
        "--video",
        default=None,
        metavar="PATH",
        help="Optional video source for bg / kaleidoscope previews",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        aspect = normalize_aspect(args.aspect)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    video_path = None
    if args.video:
        try:
            video_path = resolve_video_path(args.video)
        except FileNotFoundError as exc:
            raise SystemExit(str(exc)) from exc

    song_arg = args.audio_file
    song_path = song_arg
    if not os.path.isfile(song_path):
        candidate = os.path.join("audio", os.path.basename(song_arg))
        if os.path.isfile(candidate):
            song_path = candidate
        else:
            raise SystemExit(f"Audio not found: {song_arg}")

    styles = None
    if args.style:
        styles = tuple(part.strip().lower() for part in args.style.split(",") if part.strip())
        unknown = [s for s in styles if s not in LAYOUT_STYLES]
        if unknown:
            raise SystemExit(f"Unknown style(s) {unknown!r}; use a, b, and/or c")

    song_name = os.path.splitext(os.path.basename(song_path))[0]
    seed = args.seed if args.seed is not None else seed_from_song(song_name)
    print(f"Song: {song_name} | seed={seed} | aspect={aspect}")
    if styles:
        print(f"Styles: {', '.join(styles)}")
    if video_path:
        print(f"Video: {video_path}")
    paths = write_layout_previews(
        song_path,
        song_name,
        master_seed=seed,
        aspect=aspect,
        video_path=video_path,
        styles=styles,
    )
    print(f"\nWrote {len(paths)} previews:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
