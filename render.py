import os
import random
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from PIL import Image, ImageDraw

from art.covers import generate_cover
from art.generators.kaleidoscope import generate_kaleidoscope
from art.generators.mosaic import generate_mosaic
from art.generators.spiral import generate_spiral
from art.palette import WHITE, assert_not_tan
from art.rng import make_rng
from art.stills import seed_from_song
from chrome import (
    build_style_a_card,
    build_style_b_card,
    build_style_c_card,
    display_title,
    format_song_date,
    layout_style_a,
    layout_style_b,
    layout_style_c,
    logo_image,
    LOGO_SIZE_A,
    LOGO_TOP_A,
)
from layout import CANVAS
from visualizers import (
    SAMPLE_RATE,
    build_hard_cut_background_sequence,
    build_hard_cut_card_sequence,
    make_pulsing_border_clip,
    make_solid_pulse_background_clip,
    pick_accent_color,
)

AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "preview")
SHORTS_DURATION = 60
AUDIO_FADE = 1.0  # seconds in/out on the clipped window
BORDER_COLOR = WHITE
NP_COVER_SIZE = 800
KALEIDO_SIZE = 1600
BG_VARIANTS = 3
# Thicker white NP border
NP_BORDER_MIN = 16
NP_BORDER_MAX = 36

LAYOUT_A = "a"
LAYOUT_B = "b"
LAYOUT_C = "c"
LAYOUT_STYLES = (LAYOUT_A, LAYOUT_B, LAYOUT_C)


@dataclass
class RenderOptions:
    master_seed: int | None = None
    layout_style: str = LAYOUT_A
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
    fade = min(AUDIO_FADE, audio_clip.duration / 4)
    audio_clip = audio_clip.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])
    print(f"Audio clip: {start:.1f}s – {start + clip_dur:.1f}s ({clip_dur:.1f}s)")
    print(f"Audio fades: {fade:.1f}s in / out")
    return audio_clip


def _write_output(layers, canvas_size, audio_clip, song_name, style_tag: str) -> str:
    final_video = CompositeVideoClip(layers, size=canvas_size).with_audio(audio_clip)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{song_name}_SHORTS_{style_tag}_{timestamp}.mp4")
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


def _generate_kaleidoscope_stills(master_seed: int, count: int = BG_VARIANTS) -> list[Image.Image]:
    images: list[Image.Image] = []
    print(f"Generating {count} kaleidoscope stills...")
    for i in range(count):
        rng, _ = make_rng(master_seed ^ 0xCA1E10 ^ (i + 1) * 0x3333)
        canvas = generate_kaleidoscope(width=KALEIDO_SIZE, height=KALEIDO_SIZE, rng=rng)
        images.append(canvas.image.copy())
        print(f"  Kaleidoscope {i + 1}/{count}")
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
    if isinstance(background, tuple):
        frame = Image.new("RGB", canvas_size, background)
    else:
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
    """Write static preview PNGs for Style A / B / C (3 variants each)."""
    seed = master_seed if master_seed is not None else seed_from_song(song_name)
    canvas_size = CANVAS
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    cover = generate_cover(random.Random(seed ^ 0xC0C0), size=NP_COVER_SIZE)
    title = display_title(song_name)
    date = format_song_date(song_path, song_date)
    logo_bg_b = pick_accent_color(random.Random(seed ^ 0xD00D))
    logo_bg_c = pick_accent_color(random.Random(seed ^ 0xC0FFEE))
    canvas_c = pick_accent_color(random.Random(seed ^ 0xB6C010))

    card_a = build_style_a_card(cover.image, title, date)
    card_b = build_style_b_card(cover.image, title, date, logo_bg_b)

    spirals = _generate_spiral_backgrounds(seed)
    mosaics = _generate_mosaic_backgrounds(seed, canvas_size)
    kaleidos = _generate_kaleidoscope_stills(seed)

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
    for i, art in enumerate(kaleidos, 1):
        card_c = build_style_c_card(art, title, date, logo_bg_c)
        frame = _composite_preview_frame(canvas_c, card_c, style=LAYOUT_C)
        path = os.path.join(PREVIEW_DIR, f"{song_name}_STYLE_C_v{i}_{stamp}.png")
        frame.save(path)
        paths.append(path)
        print(f"Preview: {path}")
    return paths


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


def _render_style_c(song_path: str, song_name: str, master_seed: int, song_date: str | None) -> str:
    canvas_size = CANVAS
    kaleidos = _generate_kaleidoscope_stills(master_seed)

    canvas_color = pick_accent_color(random.Random(master_seed ^ 0xB6C010))
    logo_bg = pick_accent_color(random.Random(master_seed ^ 0xC0FFEE))
    title = display_title(song_name)
    date = format_song_date(song_path, song_date)
    cards = [build_style_c_card(art, title, date, logo_bg) for art in kaleidos]
    print(f"Canvas: RGB{canvas_color} | Logo bg: RGB{logo_bg} | Border: white")
    print(f"Title: {title} | Date: {date}")
    print(f"Cards: {len(cards)} kaleidoscope variants (peak cuts)")

    audio_clip = _audio_window(song_path, master_seed)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    chrome = layout_style_c(cards[0], audio_clip.duration, canvas_size)
    bg = make_solid_pulse_background_clip(
        canvas_color,
        mono,
        global_max_rms,
        audio_clip.duration,
        canvas_size,
    )
    card_seq = build_hard_cut_card_sequence(
        cards,
        mono,
        global_max_rms,
        audio_clip.duration,
    )

    layers = [
        bg,
        card_seq.with_position((chrome.card_x, chrome.card_y)),
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_C")


def render(song_path: str, song_name: str, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions()
    master_seed = options.master_seed if options.master_seed is not None else seed_from_song(song_name)
    style = (options.layout_style or LAYOUT_A).lower()
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
    return _render_style_c(song_path, song_name, master_seed, options.song_date)
