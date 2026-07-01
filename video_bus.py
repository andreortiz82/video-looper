import argparse
import os

from render import AUDIO_DIR, VIDEO_DIR, RenderOptions, render


def parse_args():
    parser = argparse.ArgumentParser(description="Batch render all audio files in audio/.")
    parser.add_argument(
        "--dest",
        choices=["yt", "insta", "both"],
        default="insta",
        help="Output destination. Default: insta",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    audio_files = sorted(f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a")))
    video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))

    if not audio_files:
        raise SystemExit("No audio files found in audio/")
    if not video_files:
        raise SystemExit("No video files found in video/")

    destinations = []
    if args.dest in ("yt", "both"):
        destinations.append(True)
    if args.dest in ("insta", "both"):
        destinations.append(False)

    dest_labels = " + ".join("YT" if d else "INSTA" for d in destinations)
    print(f"Found {len(audio_files)} audio file(s), {len(video_files)} video loop(s).")
    print(f"Processing {len(audio_files)} file(s) × {len(destinations)} destination(s) → {dest_labels}...\n")

    results = []
    for audio_file in audio_files:
        song_path = os.path.join(AUDIO_DIR, audio_file)
        song_name = os.path.splitext(audio_file)[0]
        for youtube in destinations:
            output = render(song_path, song_name, RenderOptions(youtube=youtube))
            results.append(output)

    print(f"\n{'=' * 60}")
    print(f"Batch complete — {len(results)} file(s) rendered:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
