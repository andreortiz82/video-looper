import os
import random
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from PIL import Image, ImageDraw

from art.covers import BASE_COVER_FILES, generate_cover
from art.generators.kaleidoscope import generate_kaleidoscope
from art.generators.mosaic import generate_mosaic
from art.generators.spiral import generate_spiral
from art.kaleido_sampler import cover_fit, kaleidoscope_from_image
from art.palette import WHITE, assert_not_tan
from art.rng import make_rng
from art.stills import seed_from_song
from chrome import (
    LayoutMetrics,
    build_style_a_card,
    build_style_b_card,
    build_style_c_card,
    display_title,
    format_song_date,
    layout_metrics,
    layout_style_a,
    layout_style_b,
    layout_style_c,
    logo_image,
)
from layout import (
    ASPECT_PORTRAIT,
    aspect_tag,
    canvas_for_aspect,
    normalize_aspect,
)
from video_source import resolve_video_path, sample_even_video_frames
from visualizers import (
    SAMPLE_RATE,
    build_hard_cut_background_sequence,
    build_hard_cut_card_sequence,
    make_pulsing_border_clip,
    make_solid_pulse_background_clip,
    pick_accent_color,
)

AUDIO_DIR = "audio"
VIDEO_DIR = "video"
OUTPUT_DIR = "output"
PREVIEW_DIR = os.path.join(OUTPUT_DIR, "preview")
SHORTS_DURATION = 60
AUDIO_FADE = 1.0  # seconds in/out on the clipped window
BORDER_COLOR = WHITE
NP_COVER_SIZE = 800
KALEIDO_SIZE = 1600
BG_VARIANTS = 3

LAYOUT_A = "a"
LAYOUT_B = "b"
LAYOUT_C = "c"
LAYOUT_STYLES = (LAYOUT_A, LAYOUT_B, LAYOUT_C)


@dataclass
class RenderOptions:
    master_seed: int | None = None
    layout_style: str = LAYOUT_A
    song_date: str | None = None
    display_name: str | None = None  # chrome title; default display_title(song_name)
    # Clip control — art uses master_seed; window uses clip_seed / audio_start
    audio_start: float | None = None  # seconds; None = seeded random
    audio_duration: float | None = None  # None → SHORTS_DURATION
    clip_seed: int | None = None  # window RNG when audio_start is None
    # Unified hub
    aspect: str = ASPECT_PORTRAIT  # portrait | square | landscape
    video_path: str | None = None  # optional bg / kaleido source
    cover_filename: str | None = None  # lock cover SVG basename
    still_index: int | None = None  # 1-based preview variant; None = all


def _chrome_title(song_name: str, options: RenderOptions | None = None) -> str:
    if options and options.display_name and options.display_name.strip():
        return options.display_name.strip()
    return display_title(song_name)


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


def _audio_window(song_path: str, master_seed: int, options: RenderOptions | None = None):
    """Return (audio_clip, window_start_sec)."""
    options = options or RenderOptions()
    audio_clip = AudioFileClip(song_path)
    song_dur = audio_clip.duration
    target_dur = SHORTS_DURATION if options.audio_duration is None else float(options.audio_duration)
    if target_dur <= 0:
        audio_clip.close()
        raise ValueError(f"audio_duration must be > 0 (got {target_dur})")

    clip_dur = min(target_dur, song_dur)
    max_start = max(0.0, song_dur - clip_dur)

    if options.audio_start is not None:
        start = float(options.audio_start)
        if start < 0:
            audio_clip.close()
            raise ValueError(f"audio_start must be >= 0 (got {start})")
        if start > max_start:
            print(
                f"Warning: audio_start {start:.1f}s clamped to {max_start:.1f}s "
                f"(song {song_dur:.1f}s, duration {clip_dur:.1f}s)"
            )
            start = max_start
        if options.clip_seed is not None:
            print("Note: audio_start set; ignoring clip_seed for window selection")
    else:
        window_seed = options.clip_seed if options.clip_seed is not None else (master_seed ^ 0xA11D10)
        start = random.Random(window_seed).uniform(0, max_start) if max_start > 0 else 0.0

    audio_clip = audio_clip.subclipped(start, start + clip_dur)
    fade = min(AUDIO_FADE, audio_clip.duration / 4)
    audio_clip = audio_clip.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])
    print(f"Audio clip: {start:.1f}s – {start + clip_dur:.1f}s ({clip_dur:.1f}s)")
    print(f"Audio fades: {fade:.1f}s in / out")
    return audio_clip, start


def _write_output(
    layers,
    canvas_size,
    audio_clip,
    song_name,
    style_tag: str,
    *,
    aspect: str,
) -> str:
    final_video = CompositeVideoClip(layers, size=canvas_size).with_audio(audio_clip)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ar = aspect_tag(aspect)
    output_path = os.path.join(
        OUTPUT_DIR, f"{song_name}_{ar}_{style_tag}_{timestamp}.mp4"
    )
    print(f"Writing: {output_path}")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    audio_clip.close()
    final_video.close()
    print(f"Done: {output_path}")
    return output_path


def _np_border_clip(mono, global_max_rms, duration, canvas_size, chrome, metrics: LayoutMetrics):
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
        border_min=metrics.border_min,
        border_max=metrics.border_max,
    )


def _mosaic_grid(canvas_size: tuple[int, int]) -> tuple[int, int]:
    """Cols/rows that keep ~square cells across aspects."""
    cw, ch = canvas_size
    cols = 6 if cw <= ch else 11
    rows = max(4, int(round(cols * ch / cw)))
    if rows % 2:
        rows += 1
    return cols, rows


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
    cols, rows = _mosaic_grid(canvas_size)
    print(f"Generating {count} mosaic backgrounds ({cols}×{rows})...")
    for i in range(count):
        rng, _ = make_rng(master_seed ^ 0xBEEF01 ^ (i + 1) * 0x2222)
        mosaic = generate_mosaic(
            width=canvas_size[0],
            height=canvas_size[1],
            cols=cols,
            rows=rows,
            rng=rng,
        )
        images.append(mosaic.image.copy())
        print(f"  Mosaic {i + 1}/{count}")
    return images


def _generate_kaleidoscope_stills(master_seed: int, count: int = BG_VARIANTS) -> list[Image.Image]:
    """Procedural triangle-grid stills (feed for sampler when no video)."""
    images: list[Image.Image] = []
    print(f"Generating {count} procedural kaleidoscope stills...")
    for i in range(count):
        rng, _ = make_rng(master_seed ^ 0xCA1E10 ^ (i + 1) * 0x3333)
        canvas = generate_kaleidoscope(width=KALEIDO_SIZE, height=KALEIDO_SIZE, rng=rng)
        images.append(canvas.image.copy())
        print(f"  Kaleidoscope {i + 1}/{count}")
    return images


def _kaleido_folds(master_seed: int, index: int) -> int:
    return random.Random(master_seed ^ 0xF01D ^ (index + 1) * 0x55).choice([4, 5, 6, 7, 8])


def _sample_kaleidos(
    sources: list[Image.Image],
    master_seed: int,
) -> list[Image.Image]:
    """Apply polar kaleidoscope sampler to each source image."""
    out: list[Image.Image] = []
    for i, src in enumerate(sources):
        folds = _kaleido_folds(master_seed, i)
        rot = random.Random(master_seed ^ 0xA07A ^ (i + 1) * 0x11).uniform(0, 360)
        print(f"  Kaleido sample {i + 1}/{len(sources)}: folds={folds} rot={rot:.0f}°")
        out.append(
            kaleidoscope_from_image(
                src,
                size=KALEIDO_SIZE,
                folds=folds,
                rotation_deg=rot,
            )
        )
    return out


def _resolve_source_stills(
    master_seed: int,
    options: RenderOptions,
    *,
    canvas_size: tuple[int, int],
    window_start: float,
    window_duration: float,
    for_kaleido: bool,
) -> tuple[list[Image.Image], str]:
    """Return (stills, source_label). Video when set; else generated art."""
    video_path = None
    if options.video_path:
        video_path = resolve_video_path(options.video_path)

    if video_path:
        print(f"Sampling video source: {video_path}")
        frames = sample_even_video_frames(
            video_path,
            count=BG_VARIANTS,
            window_duration=window_duration,
            video_start=window_start,
        )
        if for_kaleido:
            return _sample_kaleidos(frames, master_seed), f"video+kaleido:{os.path.basename(video_path)}"
        fitted = [cover_fit(f, canvas_size) for f in frames]
        return fitted, f"video:{os.path.basename(video_path)}"

    if for_kaleido:
        procedural = _generate_kaleidoscope_stills(master_seed)
        return _sample_kaleidos(procedural, master_seed), "generated+kaleido"

    # Caller supplies style-specific generators when not for_kaleido and no video
    return [], "generated"


def _composite_preview_frame(
    background: Image.Image | tuple[int, int, int],
    card: Image.Image,
    *,
    style: str,
    canvas_size: tuple[int, int],
    metrics: LayoutMetrics,
    border_thickness: int | None = None,
) -> Image.Image:
    """Static review frame: bg + card + white border (+ centered logo for Style A)."""
    cw, ch = canvas_size
    thickness = border_thickness if border_thickness is not None else metrics.border_max
    if isinstance(background, tuple):
        frame = Image.new("RGB", canvas_size, background)
    else:
        frame = background.convert("RGB").resize((cw, ch), Image.Resampling.LANCZOS)
    card_rgb = card.convert("RGB")
    card_w, card_h = card_rgb.size
    card_x = (cw - card_w) // 2

    if style == LAYOUT_A:
        logo = logo_image(metrics.logo_size_a)
        logo_x = (cw - metrics.logo_size_a) // 2
        logo_y = metrics.logo_top_a
        frame.paste(logo, (logo_x, logo_y))
        card_y = logo_y + metrics.logo_size_a + metrics.card_gap_a
        ideal_y = (ch - card_h) // 2
        if ideal_y > card_y:
            card_y = ideal_y
        card_y = min(card_y, ch - card_h - metrics.bottom_margin)
    else:
        card_y = (ch - card_h) // 2

    frame.paste(card_rgb, (card_x, card_y))
    draw = ImageDraw.Draw(frame)
    for i in range(thickness):
        draw.rectangle(
            [
                card_x - thickness + i,
                card_y - thickness + i,
                card_x + card_w + thickness - i,
                card_y + card_h + thickness - i,
            ],
            outline=BORDER_COLOR,
        )
    return frame


def _normalize_preview_styles(styles: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if styles is None:
        return LAYOUT_STYLES
    if isinstance(styles, str):
        wanted = (styles.strip().lower(),)
    else:
        wanted = tuple(s.strip().lower() for s in styles)
    unknown = [s for s in wanted if s not in LAYOUT_STYLES]
    if unknown:
        raise ValueError(f"Unknown style(s) {unknown!r}; use a, b, and/or c")
    return tuple(s for s in LAYOUT_STYLES if s in wanted)


def write_layout_previews(
    song_path: str,
    song_name: str,
    *,
    master_seed: int | None = None,
    song_date: str | None = None,
    display_name: str | None = None,
    aspect: str = ASPECT_PORTRAIT,
    video_path: str | None = None,
    styles: str | tuple[str, ...] | None = None,
) -> list[str]:
    """Write static preview PNGs for Style A / B / C (3 variants each).

    Full renders lock one cover per song (`seed ^ 0xC0C0`). Previews force
    three distinct cover templates so review shows more of the base set.
    Pass ``styles='a'`` (or a tuple) to generate a subset.
    """
    seed = master_seed if master_seed is not None else seed_from_song(song_name)
    wanted = _normalize_preview_styles(styles)
    aspect = normalize_aspect(aspect)
    canvas_size = canvas_for_aspect(aspect)
    metrics = layout_metrics(canvas_size)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    title = display_name.strip() if display_name and display_name.strip() else display_title(song_name)
    date = format_song_date(song_path, song_date)
    need_covers = LAYOUT_A in wanted or LAYOUT_B in wanted
    ar = aspect_tag(aspect)
    print(f"Preview styles: {', '.join(s.upper() for s in wanted)} | seed={seed}")

    covers = []
    if need_covers:
        cover_rng = random.Random(seed ^ 0xC0C0)
        templates = list(BASE_COVER_FILES)
        cover_rng.shuffle(templates)
        for i in range(BG_VARIANTS):
            name = templates[i % len(templates)]
            cover = generate_cover(
                random.Random(seed ^ 0xC0C0 ^ (0x9E3779B9 * (i + 1))),
                size=NP_COVER_SIZE,
                filename=name,
            )
            covers.append(cover)
            print(f"Cover variant {i + 1}: {cover.filename}")

    options = RenderOptions(master_seed=seed, aspect=aspect, video_path=video_path)
    spirals: list[Image.Image] = []
    mosaics: list[Image.Image] = []
    kaleidos: list[Image.Image] = []
    # Preview uses t=0 window for video samples
    if video_path:
        need_ab = LAYOUT_A in wanted or LAYOUT_B in wanted
        if need_ab:
            bg_ab, label_ab = _resolve_source_stills(
                seed,
                options,
                canvas_size=canvas_size,
                window_start=0.0,
                window_duration=SHORTS_DURATION,
                for_kaleido=False,
            )
            if LAYOUT_A in wanted:
                spirals = bg_ab
            if LAYOUT_B in wanted:
                mosaics = bg_ab
            print(f"Preview source A/B: {label_ab}")
        if LAYOUT_C in wanted:
            kaleidos, label_c = _resolve_source_stills(
                seed,
                options,
                canvas_size=canvas_size,
                window_start=0.0,
                window_duration=SHORTS_DURATION,
                for_kaleido=True,
            )
            print(f"Preview source C: {label_c}")
    else:
        if LAYOUT_A in wanted:
            spirals = _generate_spiral_backgrounds(seed)
        if LAYOUT_B in wanted:
            mosaics = _generate_mosaic_backgrounds(seed, canvas_size)
        if LAYOUT_C in wanted:
            procedural = _generate_kaleidoscope_stills(seed)
            kaleidos = _sample_kaleidos(procedural, seed)

    paths: list[str] = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if LAYOUT_A in wanted:
        for i, bg in enumerate(spirals):
            card_a = build_style_a_card(covers[i].image, title, date, metrics=metrics)
            frame = _composite_preview_frame(
                bg, card_a, style=LAYOUT_A, canvas_size=canvas_size, metrics=metrics
            )
            path = os.path.join(PREVIEW_DIR, f"{song_name}_{ar}_STYLE_A_bg{i + 1}_{stamp}.png")
            frame.save(path)
            paths.append(path)
            print(f"Preview: {path}")
    if LAYOUT_B in wanted:
        logo_bg_b = pick_accent_color(random.Random(seed ^ 0xD00D))
        for i, bg in enumerate(mosaics):
            card_b = build_style_b_card(covers[i].image, title, date, logo_bg_b, metrics=metrics)
            frame = _composite_preview_frame(
                bg, card_b, style=LAYOUT_B, canvas_size=canvas_size, metrics=metrics
            )
            path = os.path.join(PREVIEW_DIR, f"{song_name}_{ar}_STYLE_B_bg{i + 1}_{stamp}.png")
            frame.save(path)
            paths.append(path)
            print(f"Preview: {path}")
    if LAYOUT_C in wanted:
        logo_bg_c = pick_accent_color(random.Random(seed ^ 0xC0FFEE))
        canvas_c = pick_accent_color(random.Random(seed ^ 0xB6C010))
        for i, art in enumerate(kaleidos, 1):
            card_c = build_style_c_card(art, title, date, logo_bg_c, metrics=metrics)
            frame = _composite_preview_frame(
                canvas_c, card_c, style=LAYOUT_C, canvas_size=canvas_size, metrics=metrics
            )
            path = os.path.join(PREVIEW_DIR, f"{song_name}_{ar}_STYLE_C_v{i}_{stamp}.png")
            frame.save(path)
            paths.append(path)
            print(f"Preview: {path}")
    return paths


def _render_style_a(song_path: str, song_name: str, master_seed: int, options: RenderOptions) -> str:
    aspect = normalize_aspect(options.aspect)
    canvas_size = canvas_for_aspect(aspect)
    metrics = layout_metrics(canvas_size)

    audio_clip, window_start = _audio_window(song_path, master_seed, options)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    if options.video_path:
        backgrounds, src_label = _resolve_source_stills(
            master_seed,
            options,
            canvas_size=canvas_size,
            window_start=window_start,
            window_duration=audio_clip.duration,
            for_kaleido=False,
        )
        print(f"Backgrounds: {len(backgrounds)} from {src_label}")
    else:
        backgrounds = _generate_spiral_backgrounds(master_seed)
        if options.still_index is not None:
            idx = options.still_index - 1
            if idx < 0 or idx >= len(backgrounds):
                raise ValueError(
                    f"still_index {options.still_index} out of range "
                    f"(1–{len(backgrounds)})"
                )
            backgrounds = [backgrounds[idx]]
            print(f"Backgrounds: spiral variant {options.still_index} only (rotate + zoom)")
        else:
            print(f"Backgrounds: {len(backgrounds)} spirals (peak cuts + rotate + zoom)")

    print("Generating cover...")
    cover_rng_seed = master_seed ^ 0xC0C0
    if options.still_index is not None:
        cover_rng_seed ^= 0x9E3779B9 * options.still_index
    cover = generate_cover(
        random.Random(cover_rng_seed),
        size=NP_COVER_SIZE,
        filename=options.cover_filename,
    )

    title = _chrome_title(song_name, options)
    date = format_song_date(song_path, options.song_date)
    card = build_style_a_card(cover.image, title, date, metrics=metrics)
    print(f"Cover: {cover.filename} | Border: white")
    print(f"Title: {title} | Date: {date}")

    chrome = layout_style_a(card, audio_clip.duration, canvas_size, metrics=metrics)
    bg = build_hard_cut_background_sequence(
        backgrounds,
        mono,
        global_max_rms,
        audio_clip.duration,
        canvas_size,
        rotate=not bool(options.video_path),
        revolutions=1.0,
    )

    layers = [
        bg,
        chrome.card_clip.with_position((chrome.card_x, chrome.card_y)),
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome, metrics),
        chrome.logo_clip.with_position((chrome.logo_x, chrome.logo_y)),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_A", aspect=aspect)


def _render_style_b(song_path: str, song_name: str, master_seed: int, options: RenderOptions) -> str:
    aspect = normalize_aspect(options.aspect)
    canvas_size = canvas_for_aspect(aspect)
    metrics = layout_metrics(canvas_size)

    audio_clip, window_start = _audio_window(song_path, master_seed, options)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    if options.video_path:
        backgrounds, src_label = _resolve_source_stills(
            master_seed,
            options,
            canvas_size=canvas_size,
            window_start=window_start,
            window_duration=audio_clip.duration,
            for_kaleido=False,
        )
        print(f"Backgrounds: {len(backgrounds)} from {src_label}")
    else:
        backgrounds = _generate_mosaic_backgrounds(master_seed, canvas_size)
        print(f"Backgrounds: {len(backgrounds)} mosaics (peak cuts + zoom)")

    print("Generating cover...")
    cover = generate_cover(random.Random(master_seed ^ 0xC0C0), size=NP_COVER_SIZE)

    logo_bg = pick_accent_color(random.Random(master_seed ^ 0xD00D))
    title = _chrome_title(song_name, options)
    date = format_song_date(song_path, options.song_date)
    card = build_style_b_card(cover.image, title, date, logo_bg, metrics=metrics)
    print(f"Cover: {cover.filename} | Logo bg: RGB{logo_bg} | Border: white")
    print(f"Title: {title} | Date: {date}")

    chrome = layout_style_b(card, audio_clip.duration, canvas_size, metrics=metrics)
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
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome, metrics),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_B", aspect=aspect)


def _render_style_c(song_path: str, song_name: str, master_seed: int, options: RenderOptions) -> str:
    aspect = normalize_aspect(options.aspect)
    canvas_size = canvas_for_aspect(aspect)
    metrics = layout_metrics(canvas_size)

    audio_clip, window_start = _audio_window(song_path, master_seed, options)
    print("Analyzing audio...")
    mono, global_max_rms = _analyze_audio(audio_clip)

    kaleidos, src_label = _resolve_source_stills(
        master_seed,
        options,
        canvas_size=canvas_size,
        window_start=window_start,
        window_duration=audio_clip.duration,
        for_kaleido=True,
    )
    if not kaleidos:
        procedural = _generate_kaleidoscope_stills(master_seed)
        kaleidos = _sample_kaleidos(procedural, master_seed)
        src_label = "generated+kaleido"

    canvas_color = pick_accent_color(random.Random(master_seed ^ 0xB6C010))
    logo_bg = pick_accent_color(random.Random(master_seed ^ 0xC0FFEE))
    title = _chrome_title(song_name, options)
    date = format_song_date(song_path, options.song_date)
    cards = [
        build_style_c_card(art, title, date, logo_bg, metrics=metrics) for art in kaleidos
    ]
    print(f"Canvas: RGB{canvas_color} | Logo bg: RGB{logo_bg} | Border: white")
    print(f"Title: {title} | Date: {date}")
    print(f"Cards: {len(cards)} kaleidoscope variants from {src_label} (peak cuts)")

    chrome = layout_style_c(cards[0], audio_clip.duration, canvas_size, metrics=metrics)
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
        _np_border_clip(mono, global_max_rms, audio_clip.duration, canvas_size, chrome, metrics),
    ]
    return _write_output(layers, canvas_size, audio_clip, song_name, "STYLE_C", aspect=aspect)


def render(song_path: str, song_name: str, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions()
    master_seed = options.master_seed if options.master_seed is not None else seed_from_song(song_name)
    style = (options.layout_style or LAYOUT_A).lower()
    if style not in LAYOUT_STYLES:
        raise ValueError(f"Unknown layout_style {style!r}; expected one of {LAYOUT_STYLES}")
    aspect = normalize_aspect(options.aspect)
    options.aspect = aspect
    canvas = canvas_for_aspect(aspect)

    print(f"\n{'=' * 60}")
    print(f"Rendering: {song_name} [{aspect_tag(aspect)} / layout {style.upper()}]")
    print(f"{'=' * 60}")
    print(f"Master seed: {master_seed}")
    print(f"Canvas: {canvas[0]}×{canvas[1]} ({aspect})")
    if options.video_path:
        print(f"Video source: {options.video_path}")
    if options.cover_filename:
        print(f"Cover lock: {options.cover_filename}")
    if options.still_index is not None:
        print(f"Still lock: variant {options.still_index}")
    if options.audio_start is not None:
        print(f"Audio start: {options.audio_start:.1f}s (explicit)")
    elif options.clip_seed is not None:
        print(f"Clip seed: {options.clip_seed} (art seed unchanged)")
    if options.audio_duration is not None:
        print(f"Audio duration: {options.audio_duration:.1f}s")

    if style == LAYOUT_A:
        return _render_style_a(song_path, song_name, master_seed, options)
    if style == LAYOUT_B:
        return _render_style_b(song_path, song_name, master_seed, options)
    return _render_style_c(song_path, song_name, master_seed, options)
