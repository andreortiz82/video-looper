import os

from art.stills import seed_from_song
from render import AUDIO_DIR, LAYOUT_A, LAYOUT_B, LAYOUT_C, RenderOptions, render

LAYOUT_CHOICES = {
    "1": LAYOUT_A,
    "a": LAYOUT_A,
    "2": LAYOUT_B,
    "b": LAYOUT_B,
    "3": LAYOUT_C,
    "c": LAYOUT_C,
}


def _pick_layout() -> str:
    print("\nSelect layout style:")
    print("  1. Style A — spiral background + cover Now Playing")
    print("  2. Style B — mosaic background + logo Now Playing")
    print("  3. Style C — solid color + kaleidoscope Now Playing")
    while True:
        choice = input("Enter number (or a/b/c): ").strip().lower()
        if choice in LAYOUT_CHOICES:
            return LAYOUT_CHOICES[choice]
        print("Invalid choice.")


def main():
    audio_files = sorted(
        f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a"))
    )
    if not audio_files:
        raise SystemExit("No audio files found in audio/")

    print("Select an audio file:")
    for i, name in enumerate(audio_files, 1):
        print(f"  {i}. {name}")
    while True:
        try:
            choice = int(input("Enter number: "))
            if 1 <= choice <= len(audio_files):
                break
        except ValueError:
            pass

    layout_style = _pick_layout()
    song_path = os.path.join(AUDIO_DIR, audio_files[choice - 1])
    song_name = os.path.splitext(audio_files[choice - 1])[0]
    seed = seed_from_song(song_name)
    print(f"\nSong seed: {seed} (deterministic from filename)")
    print(f"Layout: {layout_style}")

    output = render(
        song_path,
        song_name,
        RenderOptions(master_seed=seed, layout_style=layout_style),
    )
    print(f"\nDone — {output}")


if __name__ == "__main__":
    main()
