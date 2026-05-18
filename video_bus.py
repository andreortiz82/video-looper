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
VIZ_WIDTH = 800
FREQ_BAR_HEIGHT = 100
N_BARS = 48
BORDER_MIN = 3
BORDER_MAX = 18


# ---------------------------------------------------------------------------
# Visualizer clip builders
# ---------------------------------------------------------------------------

def make_freq_bars_clip(mono, duration, width, height, color, bg_color):
    window = int(SAMPLE_RATE * 0.04)
    hann = np.hanning(window)

    def make_frame(t):
        center = int(t * SAMPLE_RATE)
        start = max(0, center - window // 2)
        chunk = mono[start:min(len(mono), start + window)]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        if len(chunk) > 1:
            padded = np.zeros(window)
            padded[:len(chunk)] = chunk
            fft = np.abs(np.fft.rfft(padded * hann))
            freqs = np.fft.rfftfreq(window, 1 / SAMPLE_RATE)

            mask = (freqs >= 40) & (freqs <= 10000)
            fft_slice = fft[mask]

            if len(fft_slice) >= N_BARS:
                edges = np.logspace(0, np.log10(len(fft_slice) - 1), N_BARS + 1, dtype=int)
                edges = np.clip(edges, 0, len(fft_slice) - 1)
                bar_vals = np.array([
                    np.mean(fft_slice[edges[i]:edges[i + 1] + 1])
                    for i in range(N_BARS)
                ])
                bar_vals = bar_vals / (np.max(bar_vals) + 1e-6)
                bar_w = width // N_BARS
                for i, val in enumerate(bar_vals):
                    bar_h = max(2, int(val * height * 0.92))
                    draw.rectangle([i * bar_w + 2, height - bar_h, (i + 1) * bar_w - 2, height], fill=color)

        return np.array(img)

    return VideoClip(make_frame, duration=duration)


def make_pulsing_border_clip(mono, global_max_rms, duration, canvas_size, video_x, video_y, video_w, video_h, color, bg_color):
    window = int(SAMPLE_RATE * 0.04)

    def make_frame(t):
        center = int(t * SAMPLE_RATE)
        start = max(0, center - window // 2)
        chunk = mono[start:min(len(mono), start + window)]
        rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0
        norm = np.clip(rms / global_max_rms, 0, 1)
        thickness = int(BORDER_MIN + norm * (BORDER_MAX - BORDER_MIN))

        img = Image.new("RGB", canvas_size, bg_color)
        draw = ImageDraw.Draw(img)
        for i in range(thickness):
            draw.rectangle(
                [video_x - thickness + i, video_y - thickness + i,
                 video_x + video_w + thickness - i, video_y + video_h + thickness - i],
                outline=color
            )
        return np.array(img)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Per-file render
# ---------------------------------------------------------------------------

def render(song_path, song_name, video_path, youtube, canvas_size, label):
    print(f"\n{'='*60}")
    print(f"Rendering: {song_name} [{label}]")
    print(f"{'='*60}")

    video_clip = VideoFileClip(video_path)
    frame = video_clip.get_frame(random.uniform(0, video_clip.duration))
    fh, fw, _ = frame.shape
    canvas_color = tuple(int(c) for c in frame[random.randint(0, fh - 1), random.randint(0, fw - 1)])
    print(f"Canvas color: RGB{canvas_color}")

    audio_clip = AudioFileClip(song_path)
    if not youtube:
        max_start = max(0, audio_clip.duration - INSTAGRAM_DURATION)
        start = random.uniform(0, max_start)
        audio_clip = audio_clip.subclipped(start, start + min(INSTAGRAM_DURATION, audio_clip.duration))
        print(f"Audio clip: {start:.1f}s – {start + INSTAGRAM_DURATION:.1f}s")

    num_loops = math.ceil(audio_clip.duration / video_clip.duration)
    print(f"Looping {num_loops}x to cover {audio_clip.duration:.1f}s")
    looped_video = concatenate_videoclips([video_clip] * num_loops).with_duration(audio_clip.duration)

    print("Analyzing audio...")
    raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
    mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples

    cx = (canvas_size[0] - video_clip.w) // 2
    cy = (canvas_size[1] - video_clip.h) // 2
    video_bottom = cy + video_clip.h
    viz_color = (255, 255, 255)
    viz_x = (canvas_size[0] - VIZ_WIDTH) // 2
    viz_y = video_bottom + 24

    window_size = int(SAMPLE_RATE * 0.04)
    rms_vals = [np.sqrt(np.mean(mono[i:i + window_size] ** 2)) for i in range(0, len(mono), window_size // 4)]
    global_max_rms = max(rms_vals) + 1e-6

    background = ColorClip(size=canvas_size, color=canvas_color, duration=audio_clip.duration)
    border = make_pulsing_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, cx, cy, video_clip.w, video_clip.h, viz_color, canvas_color)
    freq_bars = make_freq_bars_clip(mono, audio_clip.duration, VIZ_WIDTH, FREQ_BAR_HEIGHT, viz_color, canvas_color)

    final_video = CompositeVideoClip([
        background,
        border,
        looped_video.with_position((cx, cy)),
        freq_bars.with_position((viz_x, viz_y)),
    ]).with_audio(audio_clip)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{song_name}_{label}_{timestamp}.mp4")
    print(f"Writing: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

    video_clip.close()
    audio_clip.close()
    final_video.close()

    print(f"Done: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

audio_files = sorted(f for f in os.listdir(AUDIO_DIR) if f.lower().endswith((".mp3", ".wav", ".aac", ".m4a")))
video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))

if not audio_files:
    raise SystemExit("No audio files found in audio/")
if not video_files:
    raise SystemExit("No video files found in video/")

print(f"Found {len(audio_files)} audio file(s), {len(video_files)} video loop(s).\n")

print("Destination:")
print("  1. YouTube (16:9)")
print("  2. Instagram (9:16, 60s)")
while True:
    try:
        dest_choice = int(input("Enter number: "))
        if dest_choice in (1, 2):
            break
    except ValueError:
        pass

youtube = dest_choice == 1
canvas_size = YOUTUBE_CANVAS if youtube else INSTAGRAM_CANVAS
label = "YT" if youtube else "INSTA"

print(f"\nProcessing {len(audio_files)} file(s) → {label}...")
results = []

for audio_file in audio_files:
    song_path = os.path.join(AUDIO_DIR, audio_file)
    song_name = os.path.splitext(audio_file)[0]
    video_file = random.choice(video_files)
    video_path = os.path.join(VIDEO_DIR, video_file)
    print(f"\nVideo loop: {video_file}")
    output = render(song_path, song_name, video_path, youtube, canvas_size, label)
    results.append(output)

print(f"\n{'='*60}")
print(f"Batch complete — {len(results)} file(s) rendered:")
for r in results:
    print(f"  {r}")
