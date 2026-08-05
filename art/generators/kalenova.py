"""Kalenova — kaleidoscope mirror grid + rasanova pop motifs."""

from __future__ import annotations

import random

from art.canvas import Canvas, Rect
from art.generators.kaleidoscope import (
    _even,
    _mirror_corner,
    _triangle_for,
)
from art.generators.rasanova import (
    PALETTES,
    _draw_eye,
    _draw_starburst,
)
from art.palette import WHITE, assert_not_tan

COMPOSITIONS = [
    "field",
    "eyes",
    "stars",
    "mixed",
]


def _mirror_positions(x: float, y: float, width: float, height: float) -> list[tuple[float, float]]:
    """Four-fold mirror of a point in the top-left quadrant."""
    return [
        (x, y),
        (width - x, y),
        (x, height - y),
        (width - x, height - y),
    ]


def _draw_colored_kaleidoscope(
    canvas: Canvas,
    width: int,
    height: int,
    tiles_x: int,
    tiles_y: int,
    colors: list[tuple[int, int, int]],
    rng: random.Random,
) -> None:
    half_x = tiles_x // 2
    half_y = tiles_y // 2
    base_corner = [[rng.randint(0, 3) for _ in range(half_x)] for _ in range(half_y)]
    base_color = [[rng.randrange(len(colors)) for _ in range(half_x)] for _ in range(half_y)]
    # Sparse fill — skip decided in the base quarter so mirrors stay consistent.
    skip = [[rng.random() < 0.22 for _ in range(half_x)] for _ in range(half_y)]

    cell_w = width / tiles_x
    cell_h = height / tiles_y

    for row in range(tiles_y):
        for col in range(tiles_x):
            flip_x = col >= half_x
            flip_y = row >= half_y
            qr = row if not flip_y else tiles_y - 1 - row
            qc = col if not flip_x else tiles_x - 1 - col
            if skip[qr][qc]:
                continue

            corner = _mirror_corner(base_corner[qr][qc], flip_x, flip_y)
            color = colors[base_color[qr][qc]]
            rect = Rect(col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            canvas.fill_polygon(_triangle_for(rect, corner), color)


def _place_motifs(
    canvas: Canvas,
    width: int,
    height: int,
    accents: list[tuple[int, int, int]],
    rng: random.Random,
    *,
    allow_eyes: bool,
    allow_stars: bool,
) -> None:
    scale = min(width, height)
    kinds: list[str] = []
    if allow_eyes:
        kinds.append("eye")
    if allow_stars:
        kinds.append("star")
    if not kinds:
        return

    for _ in range(rng.randint(1, 3)):
        kind = rng.choice(kinds)
        # Keep clear of center seam and outer edge so mirrors read cleanly.
        x = rng.uniform(width * 0.12, width * 0.38)
        y = rng.uniform(height * 0.12, height * 0.38)

        if kind == "eye":
            size = scale * rng.uniform(0.1, 0.2)
            iris = rng.choice(accents)
            for mx, my in _mirror_positions(x, y, width, height):
                _draw_eye(canvas, mx, my, size, iris=iris)
        else:
            radius = scale * rng.uniform(0.05, 0.11)
            points = rng.choice([8, 10, 12])
            star_color = rng.choice(accents + [WHITE])
            for mx, my in _mirror_positions(x, y, width, height):
                _draw_starburst(canvas, mx, my, radius, star_color, points)

    # Optional center accent (shared by all mirrors).
    if rng.random() < 0.55:
        cx, cy = width / 2, height / 2
        if allow_eyes and (not allow_stars or rng.random() < 0.55):
            _draw_eye(
                canvas,
                cx,
                cy,
                scale * rng.uniform(0.14, 0.26),
                iris=rng.choice(accents),
            )
        elif allow_stars:
            _draw_starburst(
                canvas,
                cx,
                cy,
                scale * rng.uniform(0.08, 0.16),
                rng.choice(accents + [WHITE]),
                rng.choice([10, 12, 14]),
            )


def generate_kalenova(
    *,
    width: int = 2400,
    height: int = 2400,
    composition: str | None = None,
    tiles: int | None = None,
    tiles_x: int | None = None,
    tiles_y: int | None = None,
    bg: tuple[int, int, int] | None = None,
    rng: random.Random,
) -> Canvas:
    palette = rng.choice(PALETTES)
    palette_bg = palette["bg"]
    accents_raw = palette["accents"]
    assert isinstance(palette_bg, tuple) and isinstance(accents_raw, list)
    accents = [c for c in accents_raw if isinstance(c, tuple)]
    background = bg if bg is not None else palette_bg
    assert_not_tan(background, context="kalenova background")

    composition = composition if composition is not None else rng.choice(COMPOSITIONS)
    if composition not in COMPOSITIONS:
        raise ValueError(f"Unknown composition: {composition}. Choose from {', '.join(COMPOSITIONS)}")

    if tiles is not None:
        tiles_x = tiles_x if tiles_x is not None else tiles
        tiles_y = tiles_y if tiles_y is not None else tiles
    if tiles_x is None:
        tiles_x = rng.choice([10, 12, 14, 16])
    if tiles_y is None:
        tiles_y = rng.choice([10, 12, 14, 16])
    tiles_x = _even(tiles_x)
    tiles_y = _even(tiles_y)

    # Triangle fills: white + accents (Tan reserved for eye sclera only).
    fill_colors: list[tuple[int, int, int]] = [WHITE, *accents]
    if rng.random() < 0.4:
        darkened = (
            max(0, background[0] - 30),
            max(0, background[1] - 30),
            max(0, background[2] - 30),
        )
        fill_colors.append(darkened)

    canvas = Canvas(width, height, background)
    _draw_colored_kaleidoscope(canvas, width, height, tiles_x, tiles_y, fill_colors, rng)

    allow_eyes = composition in ("eyes", "mixed")
    allow_stars = composition in ("stars", "mixed")
    if composition != "field":
        _place_motifs(
            canvas,
            width,
            height,
            accents,
            rng,
            allow_eyes=allow_eyes,
            allow_stars=allow_stars,
        )
    elif rng.random() < 0.25:
        # Rare subtle center motif even on field compositions.
        _draw_starburst(
            canvas,
            width / 2,
            height / 2,
            min(width, height) * rng.uniform(0.06, 0.12),
            rng.choice(accents + [WHITE]),
            rng.choice([10, 12]),
        )

    return canvas
