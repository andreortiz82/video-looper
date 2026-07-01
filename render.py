import math
import os
import random
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)

from layout import canvas_for_destination, compute_layout, target_video_size
from visualizers import (
    SAMPLE_RATE,
    make_pulsing_border_clip,
    make_radial_background_clip,
    sample_random_colors,
)

AUDIO_DIR = "audio"
VIDEO_DIR = "video"
OUTPUT_DIR = "output"
INSTAGRAM_DURATION = 60
BORDER_COLOR = (255, 255, 255)


@dataclass
class RenderOptions:
    youtube: bool
    video_path: str | None = None
    theme_colors: tuple[tuple[int, int, int], tuple[int, int, int]] | None = None


def sample_theme_colors(video_clip) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    frame = video_clip.get_frame(random.uniform(0, video_clip.duration))
    return sample_random_colors(frame)


def render(song_path: str, song_name: str, options: RenderOptions) -> str:
    label = "YT" if options.youtube else "INSTA"
    canvas_size = canvas_for_destination(options.youtube)

    print(f"\n{'=' * 60}")
    print(f"Rendering: {song_name} [{label}]")
    print(f"{'=' * 60}")

    video_clip = VideoFileClip(options.video_path) if options.video_path else None
    opened_here = video_clip is not None
    if video_clip is None:
        video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.lower().endswith((".mp4", ".mov", ".webm")))
        if not video_files:
            raise FileNotFoundError("No video files found in video/")
        video_path = os.path.join(VIDEO_DIR, random.choice(video_files))
        print(f"Video loop: {os.path.basename(video_path)}")
        video_clip = VideoFileClip(video_path)
        opened_here = True

    bg_color, radial_color = options.theme_colors or sample_theme_colors(video_clip)
    print(f"Background: RGB{bg_color} | Radial: RGB{radial_color}")
    print("Logo: top_left | Viz: radial | Border: pulsing")

    audio_clip = AudioFileClip(song_path)
    if not options.youtube:
        max_start = max(0, audio_clip.duration - INSTAGRAM_DURATION)
        start = random.uniform(0, max_start)
        audio_clip = audio_clip.subclipped(start, start + min(INSTAGRAM_DURATION, audio_clip.duration))
        print(f"Audio clip: {start:.1f}s – {start + INSTAGRAM_DURATION:.1f}s")

    target_size = target_video_size(canvas_size, options.youtube)
    scaled_video = video_clip.resized(width=target_size, height=target_size)

    num_loops = math.ceil(audio_clip.duration / scaled_video.duration)
    print(f"Looping {num_loops}x to cover {audio_clip.duration:.1f}s (video {target_size}px)")
    looped_video = concatenate_videoclips([scaled_video] * num_loops).with_duration(audio_clip.duration)

    print("Analyzing audio...")
    raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
    mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples

    layout = compute_layout(
        canvas_size,
        looped_video.w,
        looped_video.h,
        audio_clip.duration,
        options.youtube,
    )

    center_x = layout.video_x + layout.video_w // 2
    center_y = layout.video_y + layout.video_h // 2
    inner_radius = int(layout.video_w * 0.42)
    outer_radius = int(max(canvas_size) * 0.58)

    window_size = int(SAMPLE_RATE * 0.04)
    rms_vals = [
        np.sqrt(np.mean(mono[i:i + window_size] ** 2))
        for i in range(0, len(mono), window_size // 4)
    ]
    global_max_rms = max(rms_vals) + 1e-6

    layers = [
        make_radial_background_clip(
            mono,
            global_max_rms,
            audio_clip.duration,
            canvas_size,
            bg_color,
            radial_color,
            center_x,
            center_y,
            inner_radius,
            outer_radius,
        ),
        make_pulsing_border_clip(
            mono,
            global_max_rms,
            audio_clip.duration,
            canvas_size,
            layout.video_x,
            layout.video_y,
            layout.video_w,
            layout.video_h,
            BORDER_COLOR,
        ),
        looped_video.with_position((layout.video_x, layout.video_y)),
        layout.logo_clip.with_position((layout.logo_x, layout.logo_y)),
    ]

    final_video = CompositeVideoClip(layers).with_audio(audio_clip)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{song_name}_{label}_{timestamp}.mp4")
    print(f"Writing: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

    audio_clip.close()
    final_video.close()
    if opened_here:
        video_clip.close()

    print(f"Done: {output_path}")
    return output_path
