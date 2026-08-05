"""Now Playing cards, logos, and text chrome for Style A / Style B."""

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

# Shared NP card geometry on 1080×1920 — meta bar identical across Style A / B
NP_WIDTH = 720
META_H = 180
TITLE_SIZE = 44
DATE_SIZE = 28
TITLE_DATE_GAP = 24
COVER_INSET_B = 28
COVER_SIZE_B = META_H - 2 * COVER_INSET_B  # fills meta bar with equal inset
LOGO_TOP_A = 96
LOGO_SIZE_A = 168
CARD_GAP_A = 48


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
) -> None:
    """Shared title/date typography for Style A and Style B meta bars."""
    x0, y0, x1, y1 = box
    title_font = _font(FONT_BOLD, TITLE_SIZE)
    date_font = _font(FONT_REG, DATE_SIZE)
    # Truncate long titles
    max_w = x1 - x0 - 24
    while title and title_font.getlength(title) > max_w and len(title) > 3:
        title = title[:-2] + "…"

    title_bbox = title_font.getbbox(title)
    date_bbox = date_font.getbbox(date)
    title_h = title_bbox[3] - title_bbox[1]
    date_h = date_bbox[3] - date_bbox[1]
    block_h = title_h + TITLE_DATE_GAP + date_h
    cy = y0 + (y1 - y0 - block_h) // 2

    if align == "center":
        tx = x0 + (x1 - x0 - (title_bbox[2] - title_bbox[0])) // 2
        dx = x0 + (x1 - x0 - (date_bbox[2] - date_bbox[0])) // 2
    else:
        tx = x0
        dx = x0

    draw.text((tx, cy), title, fill=WHITE, font=title_font)
    draw.text((dx, cy + title_h + TITLE_DATE_GAP), date, fill=(180, 180, 180), font=date_font)


def build_style_a_card(
    cover: Image.Image,
    title: str,
    date: str,
    *,
    width: int = NP_WIDTH,
) -> Image.Image:
    """Cover stacked on song meta — Style A Now Playing face (no border)."""
    cover_sq = cover.convert("RGB").resize((width, width), Image.Resampling.LANCZOS)
    h = width + META_H
    card = Image.new("RGB", (width, h), SLATE)
    card.paste(cover_sq, (0, 0))
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, width, width, h], fill=SLATE)
    _draw_meta_text(draw, (0, width, width, h), title, date, align="center")
    return card


def build_style_b_card(
    cover: Image.Image,
    title: str,
    date: str,
    logo_bg: tuple[int, int, int],
    *,
    width: int = NP_WIDTH,
) -> Image.Image:
    """Large logo block + cover/meta row — Style B Now Playing face (no border)."""
    assert_not_tan(logo_bg, context="style B logo bg")
    logo = logo_image(width, bg=logo_bg)
    h = width + META_H
    card = Image.new("RGB", (width, h), SLATE)
    card.paste(logo, (0, 0))

    meta_y = width
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, meta_y, width, h], fill=SLATE)

    thumb = cover.convert("RGB").resize((COVER_SIZE_B, COVER_SIZE_B), Image.Resampling.LANCZOS)
    thumb_y = meta_y + (META_H - COVER_SIZE_B) // 2
    card.paste(thumb, (COVER_INSET_B, thumb_y))

    text_x0 = COVER_INSET_B + COVER_SIZE_B + 24
    _draw_meta_text(
        draw,
        (text_x0, meta_y, width - COVER_INSET_B, h),
        title,
        date,
        align="left",
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
    canvas_size: tuple[int, int] = (1080, 1920),
) -> ChromeLayout:
    cw, ch = canvas_size
    logo = logo_image(LOGO_SIZE_A)
    logo_clip = _image_clip(logo, duration)
    logo_x = (cw - LOGO_SIZE_A) // 2
    logo_y = LOGO_TOP_A

    card_w, card_h = card.size
    card_x = (cw - card_w) // 2
    card_y = logo_y + LOGO_SIZE_A + CARD_GAP_A
    # Keep card visually centered if vertical room allows
    ideal_y = (ch - card_h) // 2
    if ideal_y > card_y:
        card_y = ideal_y
    card_y = min(card_y, ch - card_h - 64)

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
    canvas_size: tuple[int, int] = (1080, 1920),
) -> ChromeLayout:
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
