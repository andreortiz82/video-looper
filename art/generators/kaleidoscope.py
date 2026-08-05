from __future__ import annotations

import random

from art.canvas import Canvas, Point, Rect
from art.palette import KALEIDOSCOPE_PALETTES as PALETTES
from art.palette import assert_not_tan

FLIP_X = {0: 1, 1: 0, 2: 3, 3: 2}
FLIP_Y = {0: 3, 3: 0, 1: 2, 2: 1}


def _even(n: int) -> int:
    return n if n % 2 == 0 else n + 1


def _corners(rect: Rect) -> list[Point]:
    return [
        Point(rect.x0, rect.y0),
        Point(rect.x1, rect.y0),
        Point(rect.x1, rect.y1),
        Point(rect.x0, rect.y1),
    ]


def _triangle_for(rect: Rect, corner: int) -> list[Point]:
    pts = _corners(rect)
    return [pts[corner], pts[(corner + 1) % 4], pts[(corner - 1) % 4]]


def _mirror_corner(corner: int, flip_x: bool, flip_y: bool) -> int:
    if flip_x:
        corner = FLIP_X[corner]
    if flip_y:
        corner = FLIP_Y[corner]
    return corner


def generate_kaleidoscope(
    *,
    width: int = 2400,
    height: int = 2400,
    tiles_x: int | None = None,
    tiles_y: int | None = None,
    tiles: int | None = None,
    fg: tuple[int, int, int] | None = None,
    bg: tuple[int, int, int] | None = None,
    rng: random.Random,
) -> Canvas:
    if fg is None or bg is None:
        pfg, pbg = rng.choice(PALETTES)
        fg = fg if fg is not None else pfg
        bg = bg if bg is not None else pbg
    assert_not_tan(fg, context="kaleidoscope fg")
    assert_not_tan(bg, context="kaleidoscope bg")

    if tiles is not None:
        tiles_x = tiles_x if tiles_x is not None else tiles
        tiles_y = tiles_y if tiles_y is not None else tiles

    if tiles_x is None:
        tiles_x = rng.choice([12, 14, 16, 18, 20])
    if tiles_y is None:
        tiles_y = rng.choice([12, 14, 16, 18, 20])

    tiles_x = _even(tiles_x)
    tiles_y = _even(tiles_y)

    half_x = tiles_x // 2
    half_y = tiles_y // 2

    base = [[rng.randint(0, 3) for _ in range(half_x)] for _ in range(half_y)]

    canvas = Canvas(width, height, bg)
    cell_w = width / tiles_x
    cell_h = height / tiles_y

    for row in range(tiles_y):
        for col in range(tiles_x):
            flip_x = col >= half_x
            flip_y = row >= half_y
            qr = row if not flip_y else tiles_y - 1 - row
            qc = col if not flip_x else tiles_x - 1 - col

            corner = _mirror_corner(base[qr][qc], flip_x, flip_y)
            rect = Rect(col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            canvas.fill_polygon(_triangle_for(rect, corner), fg)

    return canvas
