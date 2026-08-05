import os
import random
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip

from art.palette import assert_not_tan
from art.stills import generate_stills, seed_from_song
from layout import CANVAS, compute_layout, target_art_size
from visualizers import (
    SAMPLE_RATE,
    build_art_sequence,
    make_pulsing_border_clip,
    make_solid_background_clip,
    sample_canvas_color,
)

AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
SHORTS_DURATION = 60
BORDER_COLOR = (255, 255, 255)


@dataclass
class RenderOptions:
    master_seed: int | None = None


def render(song_path: str, song_name: str, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions()
    canvas_size = CANVAS
    master_seed = options.master_seed if options.master_seed is not None else seed_from_song(song_name)

    print(f"\n{'=' * 60}")
    print(f"Rendering: {song_name} [SHORTS]")
    print(f"{'=' * 60}")
    print(f"Master seed: {master_seed}")

    print("Generating stills...")
    still_results = generate_stills(song_name, master_seed=master_seed)
    still_images = [r.image for r in still_results]
    style = still_results[0].name if still_results else "?"
    print(f"Style: {style} × {len(still_results)} variants (cycled)")

    frames = [np.array(img.convert("RGB")) for img in still_images]
    bg_rng = random.Random(master_seed ^ 0xC0FFEE)
    bg_color = sample_canvas_color(frames, bg_rng)
    assert_not_tan(bg_color, context="video canvas")
    print(f"Canvas: RGB{bg_color}")
    print("Logo: top_left | Border: pulsing | Art: camera-on-still × 3")

    audio_clip = AudioFileClip(song_path)
    max_start = max(0, audio_clip.duration - SHORTS_DURATION)
    start = random.Random(master_seed ^ 0xA11D10).uniform(0, max_start)
    clip_dur = min(SHORTS_DURATION, audio_clip.duration)
    audio_clip = audio_clip.subclipped(start, start + clip_dur)
    print(f"Audio clip: {start:.1f}s – {start + clip_dur:.1f}s ({clip_dur:.1f}s)")

    print("Analyzing audio...")
    raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
    mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples

    window_size = int(SAMPLE_RATE * 0.04)
    rms_vals = [
        np.sqrt(np.mean(mono[i:i + window_size] ** 2))
        for i in range(0, len(mono), max(1, window_size // 4))
    ]
    global_max_rms = max(rms_vals) + 1e-6

    panel_size = target_art_size(canvas_size)
    art_sequence = build_art_sequence(
        still_images,
        mono,
        global_max_rms,
        audio_clip.duration,
        panel_size,
        master_seed,
    )

    layout = compute_layout(canvas_size, panel_size, panel_size, audio_clip.duration)

    layers = [
        make_solid_background_clip(audio_clip.duration, canvas_size, bg_color),
        art_sequence.with_position((layout.art_x, layout.art_y)),
        make_pulsing_border_clip(
            mono,
            global_max_rms,
            audio_clip.duration,
            canvas_size,
            layout.art_x,
            layout.art_y,
            layout.art_w,
            layout.art_h,
            BORDER_COLOR,
        ),
        layout.logo_clip.with_position((layout.logo_x, layout.logo_y)),
    ]

    final_video = CompositeVideoClip(layers, size=canvas_size).with_audio(audio_clip)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{song_name}_SHORTS_{timestamp}.mp4")
    print(f"Writing: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

    audio_clip.close()
    final_video.close()

    print(f"Done: {output_path}")
    return output_path
