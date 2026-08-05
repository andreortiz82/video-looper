from __future__ import annotations

import math
import random

from art.canvas import Canvas, Point, Rect
from art.palette import MOSAIC_PALETTES as PALETTES
from art.palette import SLATE, assert_not_tan

BLACK = SLATE


def _grid_cells(width: int, height: int, cols: int, rows: int, gap: float) -> list[Rect]:
    cell_w = width / cols
    cell_h = height / rows
    half_gap = gap / 2
    cells: list[Rect] = []
    for row in range(rows):
        for col in range(cols):
            cells.append(
                Rect(
                    col * cell_w + half_gap,
                    row * cell_h + half_gap,
                    (col + 1) * cell_w - half_gap,
                    (row + 1) * cell_h - half_gap,
                )
            )
    return cells


def _rand_point_in(rect: Rect, rng: random.Random, inset: float = 0.0) -> Point:
    return Point(
        rng.uniform(rect.x0 + inset, rect.x1 - inset),
        rng.uniform(rect.y0 + inset, rect.y1 - inset),
    )


def _rand_point_on_edge(rect: Rect, rng: random.Random) -> Point:
    side = rng.randint(0, 3)
    t = rng.random()
    if side == 0:
        return Point(rect.x0 + rect.width * t, rect.y0)
    if side == 1:
        return Point(rect.x1, rect.y0 + rect.height * t)
    if side == 2:
        return Point(rect.x1 - rect.width * t, rect.y1)
    return Point(rect.x0, rect.y1 - rect.height * t)


def _triangle(rect: Rect, rng: random.Random) -> list[Point]:
    style = rng.randint(0, 2)
    if style == 0:
        return [_rand_point_on_edge(rect, rng) for _ in range(3)]
    if style == 1:
        corner = rng.choice([
            Point(rect.x0, rect.y0),
            Point(rect.x1, rect.y0),
            Point(rect.x1, rect.y1),
            Point(rect.x0, rect.y1),
        ])
        return [corner, _rand_point_on_edge(rect, rng), _rand_point_in(rect, rng, inset=rect.width * 0.08)]
    return [
        Point(rect.x0, rect.y1),
        Point(rect.x1, rect.y0),
        Point(rect.x0 + rect.width * rng.uniform(0.15, 0.85), rect.y1),
    ]


def _quad(rect: Rect, rng: random.Random) -> list[Point]:
    if rng.random() < 0.5:
        return [
            Point(rect.x0, rect.y0 + rect.height * rng.uniform(0, 0.45)),
            Point(rect.x1, rect.y0 + rect.height * rng.uniform(0, 0.35)),
            Point(rect.x1 - rect.width * rng.uniform(0, 0.35), rect.y1),
            Point(rect.x0 + rect.width * rng.uniform(0, 0.35), rect.y1),
        ]
    inset = rect.width * rng.uniform(0.04, 0.22)
    return [_rand_point_in(rect, rng, inset) for _ in range(4)]


def _trapezoid(rect: Rect, rng: random.Random) -> list[Point]:
    top_inset = rect.width * rng.uniform(0, 0.4)
    bottom_inset = rect.width * rng.uniform(0, 0.4)
    if rng.random() < 0.5:
        return [
            Point(rect.x0 + top_inset, rect.y0),
            Point(rect.x1 - top_inset, rect.y0),
            Point(rect.x1 - bottom_inset, rect.y1),
            Point(rect.x0 + bottom_inset, rect.y1),
        ]
    top_inset = rect.height * rng.uniform(0, 0.4)
    bottom_inset = rect.height * rng.uniform(0, 0.4)
    return [
        Point(rect.x0, rect.y0 + top_inset),
        Point(rect.x1, rect.y0 + bottom_inset),
        Point(rect.x1, rect.y1 - bottom_inset),
        Point(rect.x0, rect.y1 - top_inset),
    ]


def _pentagon(rect: Rect, rng: random.Random) -> list[Point]:
    cx, cy = rect.center.x, rect.center.y
    radius = min(rect.width, rect.height) * rng.uniform(0.32, 0.48)
    start = rng.uniform(0, math.tau)
    return [
        Point(cx + radius * math.cos(start + i * math.tau / 5), cy + radius * math.sin(start + i * math.tau / 5))
        for i in range(5)
    ]


def _split_diagonal(rect: Rect, rng: random.Random) -> list[list[Point]]:
    if rng.random() < 0.5:
        return [
            [Point(rect.x0, rect.y0), Point(rect.x1, rect.y0), Point(rect.x1, rect.y1)],
            [Point(rect.x0, rect.y0), Point(rect.x1, rect.y1), Point(rect.x0, rect.y1)],
        ]
    t = rng.uniform(0.25, 0.75)
    mid_top = Point(rect.x0 + rect.width * t, rect.y0)
    mid_bottom = Point(rect.x0 + rect.width * (1 - t), rect.y1)
    return [
        [Point(rect.x0, rect.y0), mid_top, Point(rect.x0, rect.y1)],
        [mid_top, Point(rect.x1, rect.y0), Point(rect.x1, rect.y1), mid_bottom, Point(rect.x0, rect.y1)],
    ]


def _random_shapes(rect: Rect, rng: random.Random) -> list[list[Point]]:
    if rng.random() < 0.25:
        return _split_diagonal(rect, rng)

    makers = [_triangle, _quad, _trapezoid, _pentagon]
    return [makers[rng.randint(0, len(makers) - 1)](rect, rng)]


def generate_mosaic(
    *,
    width: int = 2400,
    height: int = 2400,
    cols: int | None = None,
    rows: int | None = None,
    gap: float | None = None,
    bg: tuple[int, int, int] = BLACK,
    rng: random.Random,
) -> Canvas:
    scale = min(width, height)
    cols = cols if cols is not None else rng.randint(6, 10)
    rows = rows if rows is not None else rng.randint(6, 10)
    gap = gap if gap is not None else scale * rng.uniform(0.008, 0.02)

    assert_not_tan(bg, context="mosaic bg")
    palette = rng.choice(PALETTES)
    canvas = Canvas(width, height, bg)
    cells = _grid_cells(width, height, cols, rows, gap)

    for cell in cells:
        shapes = _random_shapes(cell, rng)
        for shape in shapes:
            color = rng.choice(palette)
            canvas.fill_polygon(shape, color)

    return canvas
