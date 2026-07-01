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

INSTAGRAM_CANVAS = (1080, 1920)
YOUTUBE_CANVAS = (1920, 1080)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "rasanova-logo.svg")
LOGO_POSITION = "top_left"
LOGO_OPACITY = 0.92

INSTAGRAM_VIDEO_SCALE = 0.72
YOUTUBE_VIDEO_SCALE = 0.58

LOGO_WIDTH_PORTRAIT = 140
LOGO_WIDTH_LANDSCAPE = 160
LOGO_INSET = 32
LOGO_GAP = 16
BOTTOM_MARGIN = 48


def canvas_for_destination(youtube: bool) -> tuple[int, int]:
    return YOUTUBE_CANVAS if youtube else INSTAGRAM_CANVAS


def target_video_size(canvas_size: tuple[int, int], youtube: bool) -> int:
    cw, ch = canvas_size
    if youtube:
        return int(ch * YOUTUBE_VIDEO_SCALE)
    return int(cw * INSTAGRAM_VIDEO_SCALE)


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
    video_x: int
    video_y: int
    video_w: int
    video_h: int
    logo_x: int
    logo_y: int
    logo_clip: ImageClip


def compute_layout(canvas_size, video_w, video_h, duration, youtube):
    cw, ch = canvas_size
    logo_width = LOGO_WIDTH_LANDSCAPE if youtube else LOGO_WIDTH_PORTRAIT
    logo_clip = _logo_clip(duration, logo_width)
    logo_h = logo_clip.h

    logo_x = LOGO_INSET
    logo_y = LOGO_INSET
    cx = (cw - video_w) // 2
    cy = max(logo_y + logo_h + LOGO_GAP, (ch - video_h) // 2)
    cy = min(cy, ch - video_h - BOTTOM_MARGIN)

    return LayoutResult(
        video_x=cx,
        video_y=cy,
        video_w=video_w,
        video_h=video_h,
        logo_x=logo_x,
        logo_y=logo_y,
        logo_clip=logo_clip,
    )
