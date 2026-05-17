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
WAVEFORM_HEIGHT = 80
FREQ_BAR_HEIGHT = 100
N_BARS = 48
BORDER_MIN = 3
BORDER_MAX = 18


# ---------------------------------------------------------------------------
# Visualizer clip builders
# ---------------------------------------------------------------------------

def make_waveform_clip(mono, duration, width, height, color, bg_color):
    window = int(SAMPLE_RATE * 0.08)

    def make_frame(t):
        center = int(t * SAMPLE_RATE)
        start = max(0, center - window // 2)
        chunk = mono[start:min(len(mono), start + window)]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        if len(chunk) > 1:
            indices = np.linspace(0, len(chunk) - 1, width).astype(int)
            y_vals = chunk[indices]
            local = mono[max(0, center - SAMPLE_RATE // 4):center + SAMPLE_RATE // 4]
            peak = np.max(np.abs(local)) + 1e-6
            y_norm = np.clip(y_vals / peak, -1, 1)
            points = [(x, int(height / 2 - y * height / 2 * 0.85)) for x, y in enumerate(y_norm)]
            draw.line(points, fill=color, width=2)

        return np.array(img)

    return VideoClip(make_frame, duration=duration)


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

            # Focus on 40Hz–10kHz
            mask = (freqs >= 40) & (freqs <= 10000)
            fft_slice = fft[mask]

            if len(fft_slice) >= N_BARS:
                # Log-spaced bin grouping
                edges = np.logspace(0, np.log10(len(fft_slice) - 1), N_BARS + 1, dtype=int)
                edges = np.clip(edges, 0, len(fft_slice) - 1)
                bar_vals = np.array([
                    np.mean(fft_slice[edges[i]:edges[i + 1] + 1])
                    for i in range(N_BARS)
                ])
                peak = np.max(bar_vals) + 1e-6
                bar_vals = bar_vals / peak

                bar_w = width // N_BARS
                gap = 2
                for i, val in enumerate(bar_vals):
                    bar_h = max(2, int(val * height * 0.92))
                    x0 = i * bar_w + gap
                    x1 = (i + 1) * bar_w - gap
                    draw.rectangle([x0, height - bar_h, x1, height], fill=color)

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

        x0 = video_x - thickness
        y0 = video_y - thickness
        x1 = video_x + video_w + thickness
        y1 = video_y + video_h + thickness
        for i in range(thickness):
            alpha = int(255 * (1 - i / thickness))
            draw.rectangle([x0 + i, y0 + i, x1 - i, y1 - i], outline=color)

        return np.array(img)

    return VideoClip(make_frame, duration=duration)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

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
youtube = dest_choice == 1
canvas_size = YOUTUBE_CANVAS if youtube else INSTAGRAM_CANVAS
label = "YT" if youtube else "INSTA"

print("\nVisualizers (comma-separated, e.g. 1,3):")
print("  1. Waveform")
print("  2. Frequency bars")
print("  3. Pulsing border")
viz_input = input("Select: ").strip()
viz_choices = set()
for v in viz_input.split(","):
    try:
        c = int(v.strip())
        if 1 <= c <= 3:
            viz_choices.add(c)
    except ValueError:
        pass
if not viz_choices:
    viz_choices = {1}
use_waveform = 1 in viz_choices
use_freq_bars = 2 in viz_choices
use_border = 3 in viz_choices

# ---------------------------------------------------------------------------
# Load assets
# ---------------------------------------------------------------------------

video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))
if not video_files:
    raise SystemExit("No video files found in video/")

video_file = random.choice(video_files)
video_path = os.path.join(VIDEO_DIR, video_file)
print(f"\nSelected video: {video_file}")

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

# ---------------------------------------------------------------------------
# Build visualizer clips
# ---------------------------------------------------------------------------

print("Analyzing audio...")
raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples

cx = (canvas_size[0] - video_clip.w) // 2
cy = (canvas_size[1] - video_clip.h) // 2
video_bottom = cy + video_clip.h
viz_color = (255, 255, 255)
layers = []

background = ColorClip(size=canvas_size, color=canvas_color, duration=audio_clip.duration)
layers.append(background)

if use_border:
    window_size = int(SAMPLE_RATE * 0.04)
    rms_vals = [
        np.sqrt(np.mean(mono[i:i + window_size] ** 2))
        for i in range(0, len(mono), window_size // 4)
    ]
    global_max_rms = max(rms_vals) + 1e-6
    border_clip = make_pulsing_border_clip(
        mono, global_max_rms, audio_clip.duration,
        canvas_size, cx, cy, video_clip.w, video_clip.h,
        viz_color, canvas_color
    )
    layers.append(border_clip)

layers.append(looped_video.with_position((cx, cy)))

viz_y = video_bottom + 24
viz_x = (canvas_size[0] - VIZ_WIDTH) // 2

if use_waveform:
    waveform = make_waveform_clip(mono, audio_clip.duration, VIZ_WIDTH, WAVEFORM_HEIGHT, viz_color, canvas_color)
    layers.append(waveform.with_position((viz_x, viz_y)))
    viz_y += WAVEFORM_HEIGHT + 12

if use_freq_bars:
    freq_bars = make_freq_bars_clip(mono, audio_clip.duration, VIZ_WIDTH, FREQ_BAR_HEIGHT, viz_color, canvas_color)
    layers.append(freq_bars.with_position((viz_x, viz_y)))

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

final_video = CompositeVideoClip(layers).with_audio(audio_clip)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = os.path.join(OUTPUT_DIR, f"{song_name}_{label}_{timestamp}.mp4")
print(f"Writing: {output_path}")
final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

video_clip.close()
audio_clip.close()
final_video.close()

print(f"Done: {output_path}")
