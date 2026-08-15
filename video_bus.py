"""Batch-render every file in audio/ at one layout + aspect.

Examples:
  .venv/bin/python3 video_bus.py
  .venv/bin/python3 video_bus.py a
  .venv/bin/python3 video_bus.py c square
  .venv/bin/python3 video_bus.py b landscape
"""

import os
import sys

from art.stills import seed_from_song
from layout import normalize_aspect
from render import AUDIO_DIR, LAYOUT_A, LAYOUT_B, LAYOUT_C, LAYOUT_STYLES, RenderOptions, render

LAYOUT_ALIASES = {
    "a": LAYOUT_A,
    "b": LAYOUT_B,
    "c": LAYOUT_C,
}


def main():
    layout_style = LAYOUT_A
    aspect = "portrait"
    args = sys.argv[1:]
    if args:
        key = args[0].strip().lower()
        layout_style = LAYOUT_ALIASES.get(key, key)
        if layout_style not in LAYOUT_STYLES:
            raise SystemExit(f"Usage: video_bus.py [a|b|c] [portrait|square|landscape]")
    if len(args) > 1:
        try:
            aspect = normalize_aspect(args[1])
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    audio_files = sorted(
        f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a"))
    )
    if not audio_files:
        raise SystemExit("No audio files found in audio/")

    print(
        f"Found {len(audio_files)} audio file(s). "
        f"Rendering layout={layout_style} aspect={aspect} (60s window)...\n"
    )

    results = []
    for audio_file in audio_files:
        song_path = os.path.join(AUDIO_DIR, audio_file)
        song_name = os.path.splitext(audio_file)[0]
        seed = seed_from_song(song_name)
        output = render(
            song_path,
            song_name,
            RenderOptions(master_seed=seed, layout_style=layout_style, aspect=aspect),
        )
        results.append(output)

    print(f"\n{'=' * 60}")
    print(f"Batch complete — {len(results)} file(s) rendered:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
