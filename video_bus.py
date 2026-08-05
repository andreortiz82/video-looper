import os

from render import AUDIO_DIR, RenderOptions, render
from art.stills import seed_from_song


def main():
    audio_files = sorted(
        f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a"))
    )
    if not audio_files:
        raise SystemExit("No audio files found in audio/")

    print(f"Found {len(audio_files)} audio file(s). Rendering Shorts (9:16, 60s)...\n")

    results = []
    for audio_file in audio_files:
        song_path = os.path.join(AUDIO_DIR, audio_file)
        song_name = os.path.splitext(audio_file)[0]
        seed = seed_from_song(song_name)
        output = render(song_path, song_name, RenderOptions(master_seed=seed))
        results.append(output)

    print(f"\n{'=' * 60}")
    print(f"Batch complete — {len(results)} file(s) rendered:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
