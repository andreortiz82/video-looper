"""Canvas aspect helpers and legacy layout utilities."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

try:
    import cairosvg
except OSError as exc:
    raise SystemExit(
        "cairosvg requires the Cairo system library. Install with: brew install cairo"
    ) from exc

import numpy as np
from moviepy import ImageClip
from PIL import Image

# Default Shorts canvas (9:16). Prefer canvas_for_aspect() for new code.
CANVAS = (1080, 1920)
ART_SCALE = 0.72

ASPECT_PORTRAIT = "portrait"
ASPECT_SQUARE = "square"
ASPECT_LANDSCAPE = "landscape"
ASPECTS = (ASPECT_PORTRAIT, ASPECT_SQUARE, ASPECT_LANDSCAPE)

# Named aspects → (width, height). Long edge 1920 for landscape; short edge 1080.
ASPECT_SIZES: dict[str, tuple[int, int]] = {
    ASPECT_PORTRAIT: (1080, 1920),  # 9:16
    ASPECT_SQUARE: (1080, 1080),  # 1:1
    ASPECT_LANDSCAPE: (1920, 1080),  # 16:9
}

ASPECT_ALIASES = {
    "portrait": ASPECT_PORTRAIT,
    "9:16": ASPECT_PORTRAIT,
    "shorts": ASPECT_PORTRAIT,
    "square": ASPECT_SQUARE,
    "1:1": ASPECT_SQUARE,
    "landscape": ASPECT_LANDSCAPE,
    "16:9": ASPECT_LANDSCAPE,
}

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "rasanova-logo.svg")
LOGO_OPACITY = 0.92
LOGO_WIDTH = 140
LOGO_INSET = 32
LOGO_GAP = 16
BOTTOM_MARGIN = 48


def normalize_aspect(aspect: str | None) -> str:
    if aspect is None:
        return ASPECT_PORTRAIT
    key = aspect.strip().lower()
    if key not in ASPECT_ALIASES:
        raise ValueError(
            f"Unknown aspect {aspect!r}; expected one of "
            f"{ASPECT_PORTRAIT}, {ASPECT_SQUARE}, {ASPECT_LANDSCAPE} "
            f"(or 9:16 / 1:1 / 16:9)"
        )
    return ASPECT_ALIASES[key]


def canvas_for_aspect(aspect: str | None = None) -> tuple[int, int]:
    name = normalize_aspect(aspect)
    return ASPECT_SIZES[name]


def aspect_tag(aspect: str | None = None) -> str:
    """Short label for output filenames."""
    name = normalize_aspect(aspect)
    return {
        ASPECT_PORTRAIT: "9x16",
        ASPECT_SQUARE: "1x1",
        ASPECT_LANDSCAPE: "16x9",
    }[name]


def target_art_size(canvas_size: tuple[int, int] = CANVAS) -> int:
    return int(canvas_size[0] * ART_SCALE)


def _rasterize_logo(target_width: int) -> Image.Image:
    png_data = cairosvg.svg2png(url=LOGO_PATH, output_width=target_width)
    return Image.open(io.BytesIO(png_data)).convert("RGBA")


def _logo_clip(duration: float, logo_width: int) -> ImageClip:
    logo = _rasterize_logo(logo_width)
    arr = np.array(logo)
    rgb = arr[:, :, :3]
    mask = (arr[:, :, 3].astype(float) / 255.0) * LOGO_OPACITY
    clip = ImageClip(rgb).with_duration(duration)
    return clip.with_mask(ImageClip(mask, is_mask=True).with_duration(duration))


@dataclass
class LayoutResult:
    art_x: int
    art_y: int
    art_w: int
    art_h: int
    logo_x: int
    logo_y: int
    logo_clip: ImageClip


def compute_layout(canvas_size, art_w, art_h, duration):
    cw, ch = canvas_size
    logo_clip = _logo_clip(duration, LOGO_WIDTH)
    logo_h = logo_clip.h

    logo_x = LOGO_INSET
    logo_y = LOGO_INSET
    cx = (cw - art_w) // 2
    cy = max(logo_y + logo_h + LOGO_GAP, (ch - art_h) // 2)
    cy = min(cy, ch - art_h - BOTTOM_MARGIN)

    return LayoutResult(
        art_x=cx,
        art_y=cy,
        art_w=art_w,
        art_h=art_h,
        logo_x=logo_x,
        logo_y=logo_y,
        logo_clip=logo_clip,
    )
