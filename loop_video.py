import os
import random

from render import AUDIO_DIR, VIDEO_DIR, RenderOptions, render, sample_theme_colors
from moviepy import VideoFileClip


def main():
    audio_files = sorted(f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a")))
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

    print("\nDestination (comma-separated, e.g. 1,2):")
    print("  1. YouTube (16:9)")
    print("  2. Instagram (9:16, 60s)")
    while True:
        raw = input("Select: ").strip()
        destinations = set()
        for v in raw.split(","):
            try:
                c = int(v.strip())
                if c in (1, 2):
                    destinations.add(c)
            except ValueError:
                pass
        if destinations:
            break

    video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))
    if not video_files:
        raise SystemExit("No video files found in video/")

    video_file = random.choice(video_files)
    video_path = os.path.join(VIDEO_DIR, video_file)
    print(f"\nSelected video: {video_file}")

    temp_clip = VideoFileClip(video_path)
    theme_colors = sample_theme_colors(temp_clip)
    temp_clip.close()

    results = []
    for dest in sorted(destinations):
        youtube = dest == 1
        label = "YT" if youtube else "INSTA"
        print(f"\n--- Rendering {label} ---")
        output = render(
            song_path,
            song_name,
            RenderOptions(
                youtube=youtube,
                video_path=video_path,
                theme_colors=theme_colors,
            ),
        )
        results.append(output)

    print(f"\nDone — {len(results)} file(s) rendered:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
