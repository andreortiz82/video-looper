import os

from art.stills import seed_from_song
from render import AUDIO_DIR, LAYOUT_A, LAYOUT_B, LAYOUT_C, RenderOptions, render
from video_source import list_videos, resolve_video_path

LAYOUT_CHOICES = {
    "1": LAYOUT_A,
    "a": LAYOUT_A,
    "2": LAYOUT_B,
    "b": LAYOUT_B,
    "3": LAYOUT_C,
    "c": LAYOUT_C,
}

ASPECT_CHOICES = {
    "1": "portrait",
    "p": "portrait",
    "portrait": "portrait",
    "9:16": "portrait",
    "2": "square",
    "s": "square",
    "square": "square",
    "1:1": "square",
    "3": "landscape",
    "l": "landscape",
    "landscape": "landscape",
    "16:9": "landscape",
}


def _pick_layout() -> str:
    print("\nSelect layout style:")
    print("  1. Style A — spiral (or video) background + cover Now Playing")
    print("  2. Style B — mosaic (or video) background + logo Now Playing")
    print("  3. Style C — solid color + kaleidoscope Now Playing")
    while True:
        choice = input("Enter number (or a/b/c): ").strip().lower()
        if choice in LAYOUT_CHOICES:
            return LAYOUT_CHOICES[choice]
        print("Invalid choice.")


def _pick_aspect() -> str:
    print("\nSelect aspect ratio:")
    print("  1. Portrait 9:16 (1080×1920) — Shorts default")
    print("  2. Square 1:1 (1080×1080)")
    print("  3. Landscape 16:9 (1920×1080)")
    while True:
        choice = input("Enter number (or portrait/square/landscape): ").strip().lower()
        if choice in ASPECT_CHOICES:
            return ASPECT_CHOICES[choice]
        if not choice:
            return "portrait"
        print("Invalid choice.")


def _optional_float(prompt: str) -> float | None:
    raw = input(prompt).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        print("Invalid number — using default.")
        return None


def _optional_int(prompt: str) -> int | None:
    raw = input(prompt).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("Invalid integer — using default.")
        return None


def _pick_clip_options() -> tuple[float | None, float | None, int | None]:
    print("\nAudio window (press Enter to keep defaults):")
    audio_start = _optional_float("  Start seconds [random]: ")
    audio_duration = _optional_float("  Duration seconds [60]: ")
    clip_seed = None
    if audio_start is None:
        clip_seed = _optional_int("  Clip seed [from song seed]: ")
    if audio_start is not None and audio_start < 0:
        print("Start must be >= 0 — using random.")
        audio_start = None
    if audio_duration is not None and audio_duration <= 0:
        print("Duration must be > 0 — using 60.")
        audio_duration = None
    return audio_start, audio_duration, clip_seed


def _pick_video() -> str | None:
    videos = list_videos()
    print("\nOptional video source (background / kaleidoscope):")
    print("  0. None — generated art only [default]")
    for i, name in enumerate(videos, 1):
        print(f"  {i}. {name}")
    if not videos:
        print("  (no files in video/ — enter a path, or 0)")
    raw = input("Enter number or path: ").strip()
    if not raw or raw == "0":
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(videos):
            return resolve_video_path(os.path.join("video", videos[idx - 1]))
        print("Invalid number — skipping video.")
        return None
    try:
        return resolve_video_path(raw)
    except FileNotFoundError as exc:
        print(f"{exc} — skipping video.")
        return None


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
    aspect = _pick_aspect()
    video_path = _pick_video()
    audio_start, audio_duration, clip_seed = _pick_clip_options()
    song_path = os.path.join(AUDIO_DIR, audio_files[choice - 1])
    song_name = os.path.splitext(audio_files[choice - 1])[0]
    seed = seed_from_song(song_name)
    print(f"\nSong seed: {seed} (deterministic from filename)")
    print(f"Layout: {layout_style} | Aspect: {aspect}")
    if video_path:
        print(f"Video: {video_path}")

    output = render(
        song_path,
        song_name,
        RenderOptions(
            master_seed=seed,
            layout_style=layout_style,
            aspect=aspect,
            video_path=video_path,
            audio_start=audio_start,
            audio_duration=audio_duration,
            clip_seed=clip_seed,
        ),
    )
    print(f"\nDone — {output}")


if __name__ == "__main__":
    main()
