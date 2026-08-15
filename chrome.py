"""Now Playing cards, logos, and text chrome for Style A / B / C."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime

try:
    import cairosvg
except OSError as exc:
    raise SystemExit(
        "cairosvg requires the Cairo system library. Install with: brew install cairo"
    ) from exc

import numpy as np
from moviepy import ImageClip
from PIL import Image, ImageDraw, ImageFont

from art.palette import SLATE, WHITE, assert_not_tan

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "rasanova-logo.svg")
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"

# Reference geometry on 1080×1920 portrait — scaled via LayoutMetrics
_REF_W = 1080
_REF_H = 1920
_REF_NP_WIDTH = 720
_REF_META_H = 180
_REF_TITLE = 44
_REF_DATE = 28
_REF_GAP = 24
_REF_META_INSET = 28
_REF_LOGO_TOP_A = 96
_REF_LOGO_SIZE_A = 168
_REF_CARD_GAP_A = 48
_REF_BOTTOM_MARGIN = 64

# Back-compat module-level defaults (portrait reference)
NP_WIDTH = _REF_NP_WIDTH
META_H = _REF_META_H
TITLE_SIZE = _REF_TITLE
DATE_SIZE = _REF_DATE
TITLE_DATE_GAP = _REF_GAP
META_INSET = _REF_META_INSET
META_THUMB = META_H - 2 * META_INSET
COVER_INSET_B = META_INSET
COVER_SIZE_B = META_THUMB
LOGO_TOP_A = _REF_LOGO_TOP_A
LOGO_SIZE_A = _REF_LOGO_SIZE_A
CARD_GAP_A = _REF_CARD_GAP_A


@dataclass(frozen=True)
class LayoutMetrics:
    """Aspect-aware chrome sizes derived from canvas."""

    canvas_w: int
    canvas_h: int
    np_width: int
    meta_h: int
    title_size: int
    date_size: int
    title_date_gap: int
    meta_inset: int
    meta_thumb: int
    logo_top_a: int
    logo_size_a: int
    card_gap_a: int
    bottom_margin: int
    border_min: int
    border_max: int

    @property
    def scale(self) -> float:
        return self.np_width / _REF_NP_WIDTH


def layout_metrics(canvas_size: tuple[int, int] = (_REF_W, _REF_H)) -> LayoutMetrics:
    """Fit Style A/B/C chrome to any 1:1 / 16:9 / 9:16 canvas."""
    cw, ch = canvas_size
    margin = max(24, int(min(cw, ch) * 0.03))
    border_room = 40

    # Start from width-proportional card, then shrink to fit Style A stack.
    np_w = min(int(cw * _REF_NP_WIDTH / _REF_W), cw - 2 * margin - 2 * border_room)
    np_w = max(280, np_w)

    def _from_np(width: int) -> LayoutMetrics:
        s = width / _REF_NP_WIDTH
        meta_h = max(96, int(_REF_META_H * s))
        meta_inset = max(12, int(_REF_META_INSET * s))
        meta_thumb = max(48, meta_h - 2 * meta_inset)
        return LayoutMetrics(
            canvas_w=cw,
            canvas_h=ch,
            np_width=width,
            meta_h=meta_h,
            title_size=max(18, int(_REF_TITLE * s)),
            date_size=max(14, int(_REF_DATE * s)),
            title_date_gap=max(10, int(_REF_GAP * s)),
            meta_inset=meta_inset,
            meta_thumb=meta_thumb,
            logo_top_a=max(16, int(_REF_LOGO_TOP_A * s)),
            logo_size_a=max(64, int(_REF_LOGO_SIZE_A * s)),
            card_gap_a=max(16, int(_REF_CARD_GAP_A * s)),
            bottom_margin=max(24, int(_REF_BOTTOM_MARGIN * s)),
            border_min=max(8, int(16 * s)),
            border_max=max(16, int(36 * s)),
        )

    metrics = _from_np(np_w)
    # Style A: logo_top + logo + gap + card + bottom must fit height
    for _ in range(12):
        card_h = metrics.np_width + metrics.meta_h
        needed = (
            metrics.logo_top_a
            + metrics.logo_size_a
            + metrics.card_gap_a
            + card_h
            + metrics.bottom_margin
            + border_room
        )
        if needed <= ch:
            break
        np_w = max(260, int(np_w * 0.92))
        metrics = _from_np(np_w)

    return metrics


def _font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def format_song_date(song_path: str | None = None, override: str | None = None) -> str:
    if override:
        return override
    if song_path and os.path.isfile(song_path):
        dt = datetime.fromtimestamp(os.path.getmtime(song_path))
    else:
        dt = datetime.now()
    return f"{dt:%b} {dt.day}, {dt.year}"


def display_title(song_name: str) -> str:
    """Clean leading track numbers: '07 - Gumbia' → 'Gumbia'."""
    name = song_name.strip()
    parts = name.split(" - ", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        return parts[1].strip()
    return name


def _rasterize_logo_svg(target_width: int, bg_hex: str | None = None) -> Image.Image:
    with open(LOGO_PATH, encoding="utf-8") as f:
        svg = f.read()
    if bg_hex is not None:
        svg = svg.replace('fill="black"', f'fill="{bg_hex}"')
        svg = svg.replace("fill='black'", f"fill='{bg_hex}'")
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=target_width)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def logo_image(size: int, bg: tuple[int, int, int] | None = None) -> Image.Image:
    if bg is None:
        return _rasterize_logo_svg(size).convert("RGB")
    assert_not_tan(bg, context="logo background")
    return _rasterize_logo_svg(size, bg_hex=f"#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}").convert("RGB")


def _draw_meta_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    date: str,
    *,
    align: str = "center",
    title_size: int = TITLE_SIZE,
    date_size: int = DATE_SIZE,
    title_date_gap: int = TITLE_DATE_GAP,
) -> None:
    """Shared title/date typography for Style A / B / C meta bars."""
    x0, y0, x1, y1 = box
    title_font = _font(FONT_BOLD, title_size)
    date_font = _font(FONT_REG, date_size)
    max_w = x1 - x0 - 24
    while title and title_font.getlength(title) > max_w and len(title) > 3:
        title = title[:-2] + "…"

    title_bbox = title_font.getbbox(title)
    date_bbox = date_font.getbbox(date)
    title_h = title_bbox[3] - title_bbox[1]
    date_h = date_bbox[3] - date_bbox[1]
    block_h = title_h + title_date_gap + date_h
    cy = y0 + (y1 - y0 - block_h) // 2

    if align == "center":
        tx = x0 + (x1 - x0 - (title_bbox[2] - title_bbox[0])) // 2
        dx = x0 + (x1 - x0 - (date_bbox[2] - date_bbox[0])) // 2
    else:
        tx = x0
        dx = x0

    draw.text((tx, cy), title, fill=WHITE, font=title_font)
    draw.text((dx, cy + title_h + title_date_gap), date, fill=(180, 180, 180), font=date_font)


def build_style_a_card(
    cover: Image.Image,
    title: str,
    date: str,
    *,
    width: int | None = None,
    metrics: LayoutMetrics | None = None,
) -> Image.Image:
    """Cover stacked on song meta — Style A Now Playing face (no border)."""
    m = metrics or layout_metrics((_REF_W, _REF_H))
    width = width if width is not None else m.np_width
    cover_sq = cover.convert("RGB").resize((width, width), Image.Resampling.LANCZOS)
    h = width + m.meta_h
    card = Image.new("RGB", (width, h), SLATE)
    card.paste(cover_sq, (0, 0))
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, width, width, h], fill=SLATE)
    _draw_meta_text(
        draw,
        (0, width, width, h),
        title,
        date,
        align="center",
        title_size=m.title_size,
        date_size=m.date_size,
        title_date_gap=m.title_date_gap,
    )
    return card


def build_style_b_card(
    cover: Image.Image,
    title: str,
    date: str,
    logo_bg: tuple[int, int, int],
    *,
    width: int | None = None,
    metrics: LayoutMetrics | None = None,
) -> Image.Image:
    """Large logo block + cover/meta row — Style B Now Playing face (no border)."""
    m = metrics or layout_metrics((_REF_W, _REF_H))
    width = width if width is not None else m.np_width
    assert_not_tan(logo_bg, context="style B logo bg")
    logo = logo_image(width, bg=logo_bg)
    h = width + m.meta_h
    card = Image.new("RGB", (width, h), SLATE)
    card.paste(logo, (0, 0))

    meta_y = width
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, meta_y, width, h], fill=SLATE)

    thumb = cover.convert("RGB").resize((m.meta_thumb, m.meta_thumb), Image.Resampling.LANCZOS)
    thumb_y = meta_y + (m.meta_h - m.meta_thumb) // 2
    card.paste(thumb, (m.meta_inset, thumb_y))

    text_x0 = m.meta_inset + m.meta_thumb + max(12, int(24 * m.scale))
    _draw_meta_text(
        draw,
        (text_x0, meta_y, width - m.meta_inset, h),
        title,
        date,
        align="left",
        title_size=m.title_size,
        date_size=m.date_size,
        title_date_gap=m.title_date_gap,
    )
    return card


def build_style_c_card(
    kaleido: Image.Image,
    title: str,
    date: str,
    logo_bg: tuple[int, int, int],
    *,
    width: int | None = None,
    metrics: LayoutMetrics | None = None,
) -> Image.Image:
    """Kaleidoscope art + logo/meta row — Style C Now Playing face (no border)."""
    m = metrics or layout_metrics((_REF_W, _REF_H))
    width = width if width is not None else m.np_width
    assert_not_tan(logo_bg, context="style C logo bg")
    art = kaleido.convert("RGB").resize((width, width), Image.Resampling.LANCZOS)
    h = width + m.meta_h
    card = Image.new("RGB", (width, h), SLATE)
    card.paste(art, (0, 0))

    meta_y = width
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, meta_y, width, h], fill=SLATE)

    logo = logo_image(m.meta_thumb, bg=logo_bg)
    logo_y = meta_y + (m.meta_h - m.meta_thumb) // 2
    card.paste(logo, (m.meta_inset, logo_y))

    text_x0 = m.meta_inset + m.meta_thumb + max(12, int(24 * m.scale))
    _draw_meta_text(
        draw,
        (text_x0, meta_y, width - m.meta_inset, h),
        title,
        date,
        align="left",
        title_size=m.title_size,
        date_size=m.date_size,
        title_date_gap=m.title_date_gap,
    )
    return card


@dataclass
class ChromeLayout:
    logo_x: int | None
    logo_y: int | None
    logo_clip: ImageClip | None
    card_x: int
    card_y: int
    card_w: int
    card_h: int
    card_clip: ImageClip


def _image_clip(image: Image.Image, duration: float) -> ImageClip:
    return ImageClip(np.array(image.convert("RGB"))).with_duration(duration)


def layout_style_a(
    card: Image.Image,
    duration: float,
    canvas_size: tuple[int, int] = (_REF_W, _REF_H),
    *,
    metrics: LayoutMetrics | None = None,
) -> ChromeLayout:
    m = metrics or layout_metrics(canvas_size)
    cw, ch = canvas_size
    logo = logo_image(m.logo_size_a)
    logo_clip = _image_clip(logo, duration)
    logo_x = (cw - m.logo_size_a) // 2
    logo_y = m.logo_top_a

    card_w, card_h = card.size
    card_x = (cw - card_w) // 2
    card_y = logo_y + m.logo_size_a + m.card_gap_a
    ideal_y = (ch - card_h) // 2
    if ideal_y > card_y:
        card_y = ideal_y
    card_y = min(card_y, ch - card_h - m.bottom_margin)

    return ChromeLayout(
        logo_x=logo_x,
        logo_y=logo_y,
        logo_clip=logo_clip,
        card_x=card_x,
        card_y=card_y,
        card_w=card_w,
        card_h=card_h,
        card_clip=_image_clip(card, duration),
    )


def layout_style_b(
    card: Image.Image,
    duration: float,
    canvas_size: tuple[int, int] = (_REF_W, _REF_H),
    *,
    metrics: LayoutMetrics | None = None,
) -> ChromeLayout:
    """Centered Now Playing card (Style B and Style C)."""
    del metrics  # card already sized; only canvas centering matters
    cw, ch = canvas_size
    card_w, card_h = card.size
    card_x = (cw - card_w) // 2
    card_y = (ch - card_h) // 2
    return ChromeLayout(
        logo_x=None,
        logo_y=None,
        logo_clip=None,
        card_x=card_x,
        card_y=card_y,
        card_w=card_w,
        card_h=card_h,
        card_clip=_image_clip(card, duration),
    )


layout_style_c = layout_style_b
