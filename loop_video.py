from moviepy import VideoFileClip, AudioFileClip, VideoClip, concatenate_videoclips, ColorClip, CompositeVideoClip
import math
import os
import random
import numpy as np
from PIL import Image, ImageDraw
from datetime import datetime

AUDIO_DIR = "audio"
VIDEO_DIR = "video"
OUTPUT_DIR = "output"

INSTAGRAM_DURATION = 60
INSTAGRAM_CANVAS = (1080, 1920)
YOUTUBE_CANVAS = (1920, 1080)

SAMPLE_RATE = 22050
WINDOW_MS = 80  # audio window per frame in milliseconds
VIZ_HEIGHT = 80
VIZ_WIDTH = 800


def make_waveform_clip(audio_samples, duration, width, height, color, bg_color):
    """Return a VideoClip that draws the audio waveform frame by frame."""
    window = int(SAMPLE_RATE * WINDOW_MS / 1000)

    def make_frame(t):
        center = int(t * SAMPLE_RATE)
        start = max(0, center - window // 2)
        end = min(len(audio_samples), start + window)
        chunk = audio_samples[start:end]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        if len(chunk) > 1:
            indices = np.linspace(0, len(chunk) - 1, width).astype(int)
            y_vals = chunk[indices]

            # Normalize against local peak for dynamic response
            local_start = max(0, center - SAMPLE_RATE // 4)
            local_end = min(len(audio_samples), center + SAMPLE_RATE // 4)
            peak = np.max(np.abs(audio_samples[local_start:local_end])) + 1e-6
            y_norm = np.clip(y_vals / peak, -1, 1)

            points = [
                (x, int(height / 2 - y * height / 2 * 0.85))
                for x, y in enumerate(y_norm)
            ]
            draw.line(points, fill=color, width=2)

        return np.array(img)

    return VideoClip(make_frame, duration=duration)


# --- 1. Pick audio ---
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
    print(f"Enter a number between 1 and {len(audio_files)}.")

song_path = os.path.join(AUDIO_DIR, audio_files[choice - 1])
song_name = os.path.splitext(audio_files[choice - 1])[0]

# --- 2. Pick destination ---
print("\nDestination:")
print("  1. YouTube (16:9)")
print("  2. Instagram (9:16, 60s)")

while True:
    try:
        dest_choice = int(input("Enter number: "))
        if dest_choice in (1, 2):
            break
    except ValueError:
        pass
    print("Enter 1 or 2.")

youtube = dest_choice == 1
canvas_size = YOUTUBE_CANVAS if youtube else INSTAGRAM_CANVAS
label = "YT" if youtube else "INSTA"

# --- 3. Pick random video ---
video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))
if not video_files:
    raise SystemExit("No video files found in video/")

video_file = random.choice(video_files)
video_path = os.path.join(VIDEO_DIR, video_file)
print(f"\nSelected video: {video_file}")

# --- 4. Sample a random color from the video for the canvas ---
video_clip = VideoFileClip(video_path)
sample_time = random.uniform(0, video_clip.duration)
frame = video_clip.get_frame(sample_time)
fh, fw, _ = frame.shape
px, py = random.randint(0, fw - 1), random.randint(0, fh - 1)
canvas_color = tuple(int(c) for c in frame[py, px])
print(f"Canvas color: RGB{canvas_color}")

# --- 5. Load audio, trim to 60s for Instagram ---
audio_clip = AudioFileClip(song_path)
if not youtube:
    max_start = max(0, audio_clip.duration - INSTAGRAM_DURATION)
    start = random.uniform(0, max_start)
    audio_clip = audio_clip.subclipped(start, start + min(INSTAGRAM_DURATION, audio_clip.duration))
    print(f"Audio clip: {start:.1f}s – {start + INSTAGRAM_DURATION:.1f}s")

# --- 6. Loop video to match audio duration ---
num_loops = math.ceil(audio_clip.duration / video_clip.duration)
print(f"Looping {num_loops}x to cover {audio_clip.duration:.1f}s")

looped_video = concatenate_videoclips([video_clip] * num_loops)
looped_video = looped_video.with_duration(audio_clip.duration)

# --- 7. Build waveform visualizer ---
print("Analyzing audio...")
raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples

# Waveform line color: white, or inverted canvas color for contrast
waveform_color = (255, 255, 255)

waveform_clip = make_waveform_clip(mono, audio_clip.duration, VIZ_WIDTH, VIZ_HEIGHT, waveform_color, canvas_color)

# Position waveform centered horizontally, below the video with a 24px gap
cx = (canvas_size[0] - video_clip.w) // 2
cy = (canvas_size[1] - video_clip.h) // 2
video_bottom = cy + video_clip.h

viz_x = (canvas_size[0] - VIZ_WIDTH) // 2
viz_y = video_bottom + 24

# --- 8. Composite ---
background = ColorClip(size=canvas_size, color=canvas_color, duration=audio_clip.duration)
centered_video = looped_video.with_position((cx, cy))
centered_waveform = waveform_clip.with_position((viz_x, viz_y))
final_video = CompositeVideoClip([background, centered_video, centered_waveform]).with_audio(audio_clip)

# --- 9. Export ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = os.path.join(OUTPUT_DIR, f"{song_name}_{label}_{timestamp}.mp4")
print(f"Writing: {output_path}")
final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

video_clip.close()
audio_clip.close()
final_video.close()

print(f"Done: {output_path}")
