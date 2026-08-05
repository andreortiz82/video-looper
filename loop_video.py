import os

from render import AUDIO_DIR, RenderOptions, render
from art.stills import seed_from_song


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

    song_path = os.path.join(AUDIO_DIR, audio_files[choice - 1])
    song_name = os.path.splitext(audio_files[choice - 1])[0]
    seed = seed_from_song(song_name)
    print(f"\nSong seed: {seed} (deterministic from filename)")

    output = render(song_path, song_name, RenderOptions(master_seed=seed))
    print(f"\nDone — {output}")


if __name__ == "__main__":
    main()
