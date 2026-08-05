"""Wavy nested-square spiral — vendored from abstract-art, brand palette only."""

from __future__ import annotations

import math
import random

from art.canvas import Canvas, Point
from art.palette import SPIRAL_PALETTES, assert_not_tan


def next_square(corners: list[Point], ratio: float) -> list[Point]:
    return [corners[i].lerp(corners[(i + 1) % 4], ratio) for i in range(4)]


def _draw_edge(
    canvas: Canvas,
    a: Point,
    b: Point,
    color: tuple[int, int, int],
    width: int,
    wave: float,
    wave_freq: int,
    size: int,
) -> None:
    if wave <= 0:
        canvas.draw_line(a, b, color, width=width)
        return

    dx, dy = b.x - a.x, b.y - a.y
    length = math.hypot(dx, dy)
    if length < 1:
        canvas.draw_line(a, b, color, width=width)
        return

    px, py = -dy / length, dx / length
    amp = length * wave
    segments = max(8, min(200, int(length / (size * 0.006))))

    coords: list[tuple[float, float]] = []
    for s in range(segments + 1):
        t = s / segments
        offset = amp * math.sin(2 * math.pi * wave_freq * t)
        coords.append((a.x + dx * t + px * offset, a.y + dy * t + py * offset))

    canvas.draw.line(coords, fill=color, width=width, joint="curve")


def generate_spiral(
    *,
    rng: random.Random,
    width: int = 2400,
    height: int = 2400,
    iterations: int | None = None,
    ratio: float | None = None,
    line_width: int | None = None,
    margin: float | None = None,
    fg: tuple[int, int, int] | None = None,
    bg: tuple[int, int, int] | None = None,
    wave: float | None = None,
    wave_freq: int | None = None,
    focus_x: float | None = None,
    focus_y: float | None = None,
) -> Canvas:
    scale = max(width, height)
    if fg is None or bg is None:
        palette_fg, palette_bg = rng.choice(SPIRAL_PALETTES)
        fg = fg if fg is not None else palette_fg
        bg = bg if bg is not None else palette_bg

    assert_not_tan(fg, context="spiral fg")
    assert_not_tan(bg, context="spiral bg")

    iterations = iterations if iterations is not None else rng.randint(180, 420)
    ratio = ratio if ratio is not None else rng.uniform(0.02, 0.055)
    line_width = line_width if line_width is not None else rng.randint(1, 5)
    margin = margin if margin is not None else rng.uniform(scale * 0.015, scale * 0.06)

    # Style A wants wavy + off-center by default for the wobble spin.
    if wave is None:
        wave = rng.uniform(0.03, 0.07)
    if wave_freq is None:
        wave_freq = rng.randint(1, 3)
    if focus_x is None:
        focus_x = rng.uniform(0.22, 0.78)
    if focus_y is None:
        focus_y = rng.uniform(0.22, 0.78)

    canvas = Canvas(width, height, bg)

    base = [
        Point(margin, margin),
        Point(width - margin, margin),
        Point(width - margin, height - margin),
        Point(margin, height - margin),
    ]

    corner_jitter = scale * rng.uniform(0.0, 0.09)
    corners = [
        Point(
            p.x + rng.uniform(-corner_jitter, corner_jitter),
            p.y + rng.uniform(-corner_jitter, corner_jitter),
        )
        for p in base
    ]

    centroid_x = sum(p.x for p in corners) / 4
    centroid_y = sum(p.y for p in corners) / 4
    shift_x = focus_x * width - centroid_x
    shift_y = focus_y * height - centroid_y
    corners = [Point(p.x + shift_x, p.y + shift_y) for p in corners]

    if rng.random() < 0.5:
        corners.reverse()

    for _ in range(iterations):
        for i in range(4):
            _draw_edge(
                canvas,
                corners[i],
                corners[(i + 1) % 4],
                fg,
                line_width,
                wave,
                wave_freq,
                scale,
            )
        corners = next_square(corners, ratio)

    return canvas
