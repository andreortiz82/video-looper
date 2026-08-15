#!/usr/bin/env python3
"""Render one MP4 for a song + layout style.

Examples:
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a --aspect square
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" c --video clip.mp4
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a --start 92.5
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" a --clip-seed 7
  .venv/bin/python3 scripts/render_song.py "04 - Whale Song.wav" b --start 30 --duration 45
  .venv/bin/python3 scripts/render_song.py "Big E.mp3" a --aspect square --seed 20260814 --start 15 --cover eyes-stack.svg --still 3
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
from render import LAYOUT_STYLES, RenderOptions, render
from video_source import resolve_video_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render one MP4 for a song + layout style (a|b|c).",
    )
    parser.add_argument("audio_file", help="Path or basename under audio/")
    parser.add_argument("style", help="Layout style: a, b, or c")
    parser.add_argument(
        "--aspect",
        default="portrait",
        metavar="AR",
        help="Canvas aspect: portrait|square|landscape (or 9:16|1:1|16:9). Default: portrait",
    )
    parser.add_argument(
        "--video",
        default=None,
        metavar="PATH",
        help="Optional video source for backgrounds / kaleidoscope (path or video/ basename)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=None,
        metavar="SEC",
        help="Audio in-point in seconds (default: seeded random window)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SEC",
        help="Clip length in seconds (default: 60)",
    )
    parser.add_argument(
        "--clip-seed",
        type=int,
        default=None,
        metavar="N",
        dest="clip_seed",
        help="Seed for random window only; art/cover seed unchanged",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Art/cover seed override (default: from song filename)",
    )
    parser.add_argument(
        "--cover",
        default=None,
        metavar="FILE",
        help="Lock cover SVG basename (e.g. eyes-stack.svg)",
    )
    parser.add_argument(
        "--still",
        type=int,
        default=None,
        metavar="N",
        dest="still_index",
        help="1-based preview variant to lock (Style A spiral + matching cover recolor)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    layout_style = args.style.strip().lower()
    if layout_style not in LAYOUT_STYLES:
        raise SystemExit(f"Unknown style {args.style!r}; use a, b, or c")

    try:
        aspect = normalize_aspect(args.aspect)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.start is not None and args.start < 0:
        raise SystemExit("--start must be >= 0")
    if args.duration is not None and args.duration <= 0:
        raise SystemExit("--duration must be > 0")
    if args.still_index is not None and args.still_index < 1:
        raise SystemExit("--still must be >= 1")

    video_path = None
    if args.video:
        try:
            video_path = resolve_video_path(args.video)
        except FileNotFoundError as exc:
            raise SystemExit(str(exc)) from exc

    song_path = args.audio_file if os.path.isabs(args.audio_file) else args.audio_file
    if not os.path.isfile(song_path):
        candidate = os.path.join("audio", os.path.basename(args.audio_file))
        if os.path.isfile(candidate):
            song_path = candidate
        else:
            raise SystemExit(f"Audio not found: {args.audio_file}")

    song_name = os.path.splitext(os.path.basename(song_path))[0]
    seed = args.seed if args.seed is not None else seed_from_song(song_name)
    print(f"Song: {song_name}")
    print(f"Layout: {layout_style}")
    print(f"Aspect: {aspect}")
    print(f"Seed: {seed}")
    if args.cover:
        print(f"Cover: {args.cover}")
    if args.still_index is not None:
        print(f"Still: {args.still_index}")
    if video_path:
        print(f"Video: {video_path}")

    out = render(
        song_path,
        song_name,
        RenderOptions(
            master_seed=seed,
            layout_style=layout_style,
            aspect=aspect,
            video_path=video_path,
            audio_start=args.start,
            audio_duration=args.duration,
            clip_seed=args.clip_seed,
            cover_filename=args.cover,
            still_index=args.still_index,
        ),
    )
    print(f"\nDone — {out}")


if __name__ == "__main__":
    main()
