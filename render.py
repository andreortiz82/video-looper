import os
import random
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip
from PIL import Image, ImageDraw

from art.covers import generate_cover
from art.generators.mosaic import generate_mosaic
from art.generators.spiral import generate_spiral
from art.palette import WHITE, assert_not_tan
from art.rng import make_rng
from art.stills import generate_stills, seed_from_song
from chrome import (
    build_style_a_card,
    build_style_b_card,
    display_title,
    format_song_date,
    layout_style_a,
    layout_style_b,
    logo_image,
    LOGO_SIZE_A,
    LOGO_TOP_A,
)
from layout import CANVAS, compute_layout, target_art_size
from visualizers import (
    SAMPLE_RATE,
    build_art_sequence,
    build_hard_cut_background_sequence,
    make_pulsing_border_clip,
    make_solid_background_clip,
    pick_accent_color,
    sample_canvas_color,
)

AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "preview")
SHORTS_DURATION = 60
BORDER_COLOR = WHITE
NP_COVER_SIZE = 800
BG_VARIANTS = 3
# Thicker white NP border (Style A / B)
NP_BORDER_MIN = 16
NP_BORDER_MAX = 36

LAYOUT_CLASSIC = "classic"
LAYOUT_A = "a"
LAYOUT_B = "b"
LAYOUT_STYLES = (LAYOUT_CLASSIC, LAYOUT_A, LAYOUT_B)


@dataclass
class RenderOptions:
    master_seed: int | None = None
    layout_style: str = LAYOUT_CLASSIC
    song_date: str | None = None


def _analyze_audio(audio_clip):
    raw_samples = audio_clip.to_soundarray(fps=SAMPLE_RATE)
    mono = raw_samples.mean(axis=1) if raw_samples.ndim > 1 else raw_samples
    window_size = int(SAMPLE_RATE * 0.04)
    rms_vals = [
        np.sqrt(np.mean(mono[i : i + window_size] ** 2))
        for i in range(0, len(mono), max(1, window_size // 4))
    ]
    global_max_rms = max(rms_vals) + 1e-6
    return mono, global_max_rms


def _audio_window(song_path: str, master_seed: int):
    audio_clip = AudioFileClip(song_path)
    max_start = max(0, audio_clip.duration - SHORTS_DURATION)
    start = random.Random(master_seed ^ 0xA11D10).uniform(0, max_start)
    clip_dur = min(SHORTS_DURATION, audio_clip.duration)
    audio_clip = audio_clip.subclipped(start, start + clip_dur)
    print(f"Audio clip: {start:.1f}s – {start + clip_dur:.1f}s ({clip_dur:.1f}s)")
    return audio_clip


def _write_output(layers, canvas_size, audio_clip, song_name, style_tag: str) -> str:
    final_video = CompositeVideoClip(layers, size=canvas_size).with_audio(audio_clip)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"SHORTS_{style_tag}" if style_tag != "CLASSIC" else "SHORTS"
    output_path = os.path.join(OUTPUT_DIR, f"{song_name}_{tag}_{timestamp}.mp4")
    print(f"Writing: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    audio_clip.close()
    final_video.close()
    print(f"Done: {output_path}")
    return output_path


def _np_border_clip(mono, global_max_rms, duration, canvas_size, chrome):
    return make_pulsing_border_clip(
        mono,
        global_max_rms,
        duration,
        canvas_size,
        chrome.card_x,
        chrome.card_y,
        chrome.card_w,
        chrome.card_h,
        BORDER_COLOR,
        border_min=NP_BORDER_MIN,
        border_max=NP_BORDER_MAX,
    )


def _generate_spiral_backgrounds(master_seed: int, count: int = BG_VARIANTS) -> list[Image.Image]:
    spiral_size = 2400
    images: list[Image.Image] = []
    print(f"Generating {count} spiral backgrounds...")
    for i in range(count):
        rng, _ = make_rng(master_seed ^ 0xA5A5A5 ^ (i + 1) * 0x1111)
        spiral = generate_spiral(
            rng=rng,
            width=spiral_size,
            height=spiral_size,
            wave=rng.uniform(0.035, 0.07),
            focus_x=rng.uniform(0.25, 0.75),
            focus_y=rng.uniform(0.25, 0.75),
        )
        assert_not_tan(spiral.image.getpixel((0, 0)), context="spiral bg")
        images.append(spiral.image.copy())
        print(f"  Spiral {i + 1}/{count}")
    return images


def _generate_mosaic_backgrounds(
    master_seed: int,
    canvas_size: tuple[int, int],
    count: int = BG_VARIANTS,
) -> list[Image.Image]:
    images: list[Image.Image] = []
    print(f"Generating {count} mosaic backgrounds...")
    for i in range(count):
        rng, _ = make_rng(master_seed ^ 0xBEEF01 ^ (i + 1) * 0x2222)
        mosaic = generate_mosaic(
            width=canvas_size[0],
            height=canvas_size[1],
            cols=6,
            rows=11,
            rng=rng,
        )
        images.append(mosaic.image.copy())
        print(f"  Mosaic {i + 1}/{count}")
    return images


def _composite_preview_frame(
    background: Image.Image,
    card: Image.Image,
    *,
    style: str,
    canvas_size: tuple[int, int] = CANVAS,
    border_thickness: int = NP_BORDER_MAX,
) -> Image.Image:
    """Static review frame: bg + card + white border (+ centered logo for Style A)."""
    cw, ch = canvas_size
    frame = background.convert("RGB").resize((cw, ch), Image.Resampling.LANCZOS)
    card_rgb = card.convert("RGB")
    card_w, card_h = card_rgb.size
    card_x = (cw - card_w) // 2

    if style == LAYOUT_A:
        logo = logo_image(LOGO_SIZE_A)
        logo_x = (cw - LOGO_SIZE_A) // 2
        logo_y = LOGO_TOP_A
        frame.paste(logo, (logo_x, logo_y))
        card_y = logo_y + LOGO_SIZE_A + 48
        ideal_y = (ch - card_h) // 2
        if ideal_y > card_y:
            card_y = ideal_y
        card_y = min(card_y, ch - card_h - 64)
    else:
        card_y = (ch - card_h) // 2

    frame.paste(card_rgb, (card_x, card_y))
    draw = ImageDraw.Draw(frame)
    for i in range(border_thickness):
        draw.rectangle(
            [
                card_x - border_thickness + i,
                card_y - border_thickness + i,
                card_x + card_w + border_thickness - i,
                card_y + card_h + border_thickness - i,
            ],
            outline=BORDER_COLOR,
        )
    return frame


def write_layout_previews(
    song_path: str,
    song_name: str,
    *,
    master_seed: int | None = None,
    song_date: str | None = None,
) -> list[str]:
    """Write static preview PNGs for Style A/B × 3 background variants."""
    seed = master_seed if master_seed is not None else seed_from_song(song_name)
    canvas_size = CANVAS
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    cover = generate_cover(random.Random(seed ^ 0xC0C0), size=NP_COVER_SIZE)
    title = display_title(song_name)
    date = format_song_date(song_path, song_date)
    logo_bg = pick_accent_color(random.Random(seed ^ 0xD00D))

    card_a = build_style_a_card(cover.image, title, date)
    card_b = build_style_b_card(cover.image, title, date, logo_bg)

    spirals = _generate_spiral_backgrounds(seed)
    mosaics = _generate_mosaic_backgrounds(seed, canvas_size)

    paths: list[str] = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, bg in enumerate(spirals, 1):
        frame = _composite_preview_frame(bg, card_a, style=LAYOUT_A)
        path = os.path.join(PREVIEW_DIR, f"{song_name}_STYLE_A_bg{i}_{stamp}.png")
        frame.save(path)
        paths.append(path)
        print(f"Preview: {path}")
    for i, bg in enumerate(mosaics, 1):
        frame = _composite_preview_frame(bg, card_b, style=LAYOUT_B)
        path = os.path.join(PREVIEW_DIR, f"{song_name}_STYLE_B_bg{i}_{stamp}.png")
        frame.save(path)
        paths.append(path)
        print(f"Preview: {path}")
    return paths


def _render_classic(song_path: str, song_name: str, master_seed: int) -> str:
    canvas_size = CANVAS
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

    audio_clip = _audio_window(song_path, master_seed)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

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
    return _write_output(layers, canvas_size, audio_clip, song_name, "CLASSIC")


def _render_style_a(song_path: str, song_name: str, master_seed: int, song_date: str | None) -> str:
    canvas_size = CANVAS
    backgrounds = _generate_spiral_backgrounds(master_seed)

    print("Generating cover...")
    cover = generate_cover(random.Random(master_seed ^ 0xC0C0), size=NP_COVER_SIZE)

    title = display_title(song_name)
    date = format_song_date(song_path, song_date)
    card = build_style_a_card(cover.image, title, date)
    print(f"Cover: {cover.filename} | Border: white")
    print(f"Title: {title} | Date: {date}")
    print(f"Backgrounds: {len(backgrounds)} spirals (peak cuts + rotate + zoom)")

    audio_clip = _audio_window(song_path, master_seed)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    chrome = layout_style_a(card, audio_clip.duration, canvas_size)
    bg = build_hard_cut_background_sequence(
        backgrounds,
        mono,
        global_max_rms,
        audio_clip.duration,
        canvas_size,
        rotate=True,
        revolutions=1.0,
    )

    layers = [
        bg,
        chrome.card_clip.with_position((chrome.card_x, chrome.card_y)),
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome),
        chrome.logo_clip.with_position((chrome.logo_x, chrome.logo_y)),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_A")


def _render_style_b(song_path: str, song_name: str, master_seed: int, song_date: str | None) -> str:
    canvas_size = CANVAS
    backgrounds = _generate_mosaic_backgrounds(master_seed, canvas_size)

    print("Generating cover...")
    cover = generate_cover(random.Random(master_seed ^ 0xC0C0), size=NP_COVER_SIZE)

    logo_bg = pick_accent_color(random.Random(master_seed ^ 0xD00D))
    title = display_title(song_name)
    date = format_song_date(song_path, song_date)
    card = build_style_b_card(cover.image, title, date, logo_bg)
    print(f"Cover: {cover.filename} | Logo bg: RGB{logo_bg} | Border: white")
    print(f"Title: {title} | Date: {date}")
    print(f"Backgrounds: {len(backgrounds)} mosaics (peak cuts + zoom)")

    audio_clip = _audio_window(song_path, master_seed)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    chrome = layout_style_b(card, audio_clip.duration, canvas_size)
    bg = build_hard_cut_background_sequence(
        backgrounds,
        mono,
        global_max_rms,
        audio_clip.duration,
        canvas_size,
        rotate=False,
    )

    layers = [
        bg,
        chrome.card_clip.with_position((chrome.card_x, chrome.card_y)),
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_B")


def render(song_path: str, song_name: str, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions()
    master_seed = options.master_seed if options.master_seed is not None else seed_from_song(song_name)
    style = (options.layout_style or LAYOUT_CLASSIC).lower()
    if style not in LAYOUT_STYLES:
        raise ValueError(f"Unknown layout_style {style!r}; expected one of {LAYOUT_STYLES}")

    print(f"\n{'=' * 60}")
    print(f"Rendering: {song_name} [SHORTS / layout {style.upper()}]")
    print(f"{'=' * 60}")
    print(f"Master seed: {master_seed}")

    if style == LAYOUT_A:
        return _render_style_a(song_path, song_name, master_seed, options.song_date)
    if style == LAYOUT_B:
        return _render_style_b(song_path, song_name, master_seed, options.song_date)
    return _render_classic(song_path, song_name, master_seed)
