"""N-fold polar kaleidoscope from a source image (still or video frame).

Pillow + NumPy only — no GLSL / ModernGL / Butterchurn.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image


def cover_crop(image: Image.Image, size: int) -> Image.Image:
    """Center-crop to square then resize to ``size``."""
    src = image.convert("RGB")
    w, h = src.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    cropped = src.crop((left, top, left + side, top + side))
    return cropped.resize((size, size), Image.Resampling.LANCZOS)


def cover_fit(image: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    """Scale + center-crop to fill ``canvas_size`` (cover fit)."""
    cw, ch = canvas_size
    src = image.convert("RGB")
    sw, sh = src.size
    scale = max(cw / sw, ch / sh)
    nw = max(cw, int(math.ceil(sw * scale)))
    nh = max(ch, int(math.ceil(sh * scale)))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - cw) // 2
    top = (nh - ch) // 2
    return resized.crop((left, top, left + cw, top + ch))


def kaleidoscope_from_image(
    source: Image.Image,
    *,
    size: int = 1600,
    folds: int = 6,
    rotation_deg: float = 0.0,
) -> Image.Image:
    """Sample ``source`` through an N-fold polar mirror into a square RGB image.

    Each sector mirrors a wedge of the cover-cropped source. ``folds`` should
    be >= 3 (typical 4–10). ``rotation_deg`` rotates the fold pattern.
    """
    if folds < 3:
        raise ValueError(f"folds must be >= 3 (got {folds})")

    square = cover_crop(source, size)
    src = np.asarray(square, dtype=np.float32)
    h, w = src.shape[:2]
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    radius = np.sqrt(dx * dx + dy * dy)
    angle = np.arctan2(dy, dx)  # [-pi, pi]

    sector = (2.0 * math.pi) / folds
    # Rotate fold axes, wrap into one sector, then mirror half-sector.
    a = angle - math.radians(rotation_deg)
    a = (a + math.pi) % (2.0 * math.pi) - math.pi
    a = a % sector
    half = sector / 2.0
    a = np.where(a > half, sector - a, a)

    # Map mirrored polar coords back into source cartesian.
    sx = cx + radius * np.cos(a)
    sy = cy + radius * np.sin(a)
    sx = np.clip(sx, 0, w - 1)
    sy = np.clip(sy, 0, h - 1)

    # Bilinear sample
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    wx = sx - x0
    wy = sy - y0

    out = np.empty_like(src)
    for c in range(3):
        p00 = src[y0, x0, c]
        p10 = src[y0, x1, c]
        p01 = src[y1, x0, c]
        p11 = src[y1, x1, c]
        top = p00 * (1 - wx) + p10 * wx
        bot = p01 * (1 - wx) + p11 * wx
        out[:, :, c] = top * (1 - wy) + bot * wy

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGB")
