"""Mosaova — mosaic grid geometry × rasanova pop motifs."""

from __future__ import annotations

import random

from art.canvas import Canvas
from art.generators.mosaic import (
    _grid_cells,
    _random_shapes,
)
from art.generators.rasanova import (
    _draw_eye,
    _draw_starburst,
)
from art.palette import ACCENTS, BACKGROUNDS, RASANOVA_PALETTES, SLATE, WHITE, assert_not_tan


def generate_mosaova(
    *,
    width: int = 2400,
    height: int = 2400,
    cols: int | None = None,
    rows: int | None = None,
    gap: float | None = None,
    bg: tuple[int, int, int] | None = None,
    rng: random.Random,
) -> Canvas:
    scale = min(width, height)
    cols = cols if cols is not None else rng.randint(6, 10)
    rows = rows if rows is not None else rng.randint(6, 10)
    gap = gap if gap is not None else scale * rng.uniform(0.008, 0.02)

    palette = rng.choice(RASANOVA_PALETTES)
    accents_raw = palette["accents"]
    assert isinstance(accents_raw, list)
    accents = [c for c in accents_raw if isinstance(c, tuple)]
    if not accents:
        accents = ACCENTS[:]

    palette_bg = palette["bg"]
    assert isinstance(palette_bg, tuple)
    background = bg if bg is not None else palette_bg
    if background not in BACKGROUNDS and bg is None:
        background = rng.choice(BACKGROUNDS)
    assert_not_tan(background, context="mosaova background")

    fill_colors: list[tuple[int, int, int]] = [WHITE, *accents]
    canvas = Canvas(width, height, background)
    cells = _grid_cells(width, height, cols, rows, gap)

    motif_budget = max(2, int(len(cells) * rng.uniform(0.08, 0.16)))
    motif_indices = set(rng.sample(range(len(cells)), min(motif_budget, len(cells))))

    for idx, cell in enumerate(cells):
        shapes = _random_shapes(cell, rng)
        for shape in shapes:
            canvas.fill_polygon(shape, rng.choice(fill_colors))

        if idx not in motif_indices:
            continue

        cx, cy = cell.center.x, cell.center.y
        cell_scale = min(cell.width, cell.height)
        if rng.random() < 0.55:
            _draw_eye(
                canvas,
                cx,
                cy,
                cell_scale * rng.uniform(0.55, 0.85),
                iris=rng.choice(accents),
            )
        else:
            _draw_starburst(
                canvas,
                cx,
                cy,
                cell_scale * rng.uniform(0.28, 0.45),
                rng.choice(accents + [WHITE, SLATE]),
                rng.choice([8, 10, 12]),
            )

    return canvas
