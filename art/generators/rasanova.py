from __future__ import annotations

import math
import random
from typing import Callable

from art.canvas import Canvas, Point, Rect
from art.palette import EYE_SCLERA, RASANOVA_PALETTES, SLATE, WHITE, assert_not_tan

BLACK = SLATE
PALETTES = RASANOVA_PALETTES
# Tan/EYE_SCLERA only via _draw_eye default sclera — never as composition fills.

COMPOSITIONS = [
    "eye_grid",
    "eye_column",
    "starburst_solo",
    "star_eye_shadow",
    "triangle_solo",
    "checker_center",
    "mixed",
]


def _star_points(cx: float, cy: float, outer_r: float, inner_r: float, points: int = 12) -> list[Point]:
    verts: list[Point] = []
    for i in range(points * 2):
        angle = i * math.pi / points - math.pi / 2
        radius = outer_r if i % 2 == 0 else inner_r
        verts.append(Point(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return verts


def _triangle_points(cx: float, cy: float, size: float, pointing_up: bool) -> list[Point]:
    h = size * math.sqrt(3) / 2
    if pointing_up:
        return [
            Point(cx, cy - h * 0.58),
            Point(cx - size / 2, cy + h * 0.42),
            Point(cx + size / 2, cy + h * 0.42),
        ]
    return [
        Point(cx, cy + h * 0.58),
        Point(cx - size / 2, cy - h * 0.42),
        Point(cx + size / 2, cy - h * 0.42),
    ]


def _eye_sclera_points(cx: float, cy: float, half_w: float, half_h: float, segments: int = 48) -> list[Point]:
    """Pointed almond (vesica) sclera: two circular arcs meeting at sharp left/right tips."""
    a, b = half_w, half_h
    if b <= 0 or a <= b:
        # Degenerate / too round — fall back to a slim lens via clamped height.
        b = min(b, a * 0.85) if b > 0 else a * 0.35
        b = max(b, 1e-3)
    # Upper/lower circle centers in local coords (y down). Tips at (±a, 0); bulge ±b.
    cu = (a * a - b * b) / (2.0 * b)
    r = math.hypot(a, cu)
    # Angles from each center to the left tip (arc sweeps left → right for upper).
    upper_c = (0.0, cu)
    lower_c = (0.0, -cu)
    theta_left_u = math.atan2(0.0 - upper_c[1], -a - upper_c[0])
    theta_right_u = math.atan2(0.0 - upper_c[1], a - upper_c[0])
    theta_left_l = math.atan2(0.0 - lower_c[1], -a - lower_c[0])
    theta_right_l = math.atan2(0.0 - lower_c[1], a - lower_c[0])

    pts: list[Point] = []
    for i in range(segments + 1):
        t = i / segments
        ang = theta_left_u + (theta_right_u - theta_left_u) * t
        pts.append(Point(cx + upper_c[0] + r * math.cos(ang), cy + upper_c[1] + r * math.sin(ang)))
    for i in range(1, segments + 1):
        t = i / segments
        ang = theta_right_l + (theta_left_l - theta_right_l) * t
        pts.append(Point(cx + lower_c[0] + r * math.cos(ang), cy + lower_c[1] + r * math.sin(ang)))
    return pts


def _draw_eye(
    canvas: Canvas,
    cx: float,
    cy: float,
    size: float,
    *,
    sclera: tuple[int, int, int] = EYE_SCLERA,
    iris: tuple[int, int, int],
    pupil: tuple[int, int, int] = BLACK,
) -> None:
    half_w = size / 2
    half_h = size * 0.32
    canvas.fill_polygon(_eye_sclera_points(cx, cy, half_w, half_h), sclera)
    # Iris nearly fills vertical height of the almond.
    iris_r = half_h * 0.92
    canvas.draw_ellipse(Rect(cx - iris_r, cy - iris_r, cx + iris_r, cy + iris_r), fill=iris)
    pupil_r = iris_r * 0.38
    canvas.draw_ellipse(Rect(cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r), fill=pupil)


def _draw_starburst(canvas: Canvas, cx: float, cy: float, radius: float, color: tuple[int, int, int], points: int) -> None:
    inner = radius * 0.42
    canvas.fill_polygon(_star_points(cx, cy, radius, inner, points), color)


def _draw_long_shadow(
    canvas: Canvas,
    shape_points: list[Point],
    shadow_color: tuple[int, int, int],
    length: float,
    angle: float = math.pi / 4,
) -> None:
    dx = math.cos(angle) * length
    dy = math.sin(angle) * length
    shadow = [Point(p.x + dx, p.y + dy) for p in shape_points]
    for i in range(len(shape_points)):
        j = (i + 1) % len(shape_points)
        quad = [shape_points[i], shape_points[j], shadow[j], shadow[i]]
        canvas.fill_polygon(quad, shadow_color)


def _draw_colored_checker(
    canvas: Canvas,
    rect: Rect,
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    rng: random.Random,
) -> None:
    tiles = rng.randint(4, 8)
    tile_w = rect.width / tiles
    tile_h = rect.height / tiles
    rows = int(math.ceil(rect.height / tile_h))
    for row in range(rows):
        for col in range(tiles):
            fill = color_a if (row + col) % 2 == 0 else color_b
            x0 = rect.x0 + col * tile_w
            y0 = rect.y0 + row * tile_h
            canvas.fill_rect(Rect(x0, y0, x0 + tile_w, y0 + tile_h), fill)


def _draw_dot_texture(
    canvas: Canvas,
    rect: Rect,
    bg: tuple[int, int, int],
    dot: tuple[int, int, int],
    rng: random.Random,
) -> None:
    canvas.fill_rect(rect, bg)
    cols = rng.randint(5, 9)
    spacing = rect.width / cols
    radius = spacing * rng.uniform(0.14, 0.28)
    y = rect.y0 + spacing / 2
    while y < rect.y1:
        x = rect.x0 + spacing / 2
        while x < rect.x1:
            canvas.draw_ellipse(
                Rect(x - radius, y - radius, x + radius, y + radius),
                fill=dot,
            )
            x += spacing
        y += spacing


def _draw_stripe_texture(
    canvas: Canvas,
    rect: Rect,
    bg: tuple[int, int, int],
    stripe: tuple[int, int, int],
    rng: random.Random,
    *,
    vertical: bool,
) -> None:
    canvas.fill_rect(rect, bg)
    span = rect.width if vertical else rect.height
    count = rng.randint(6, 12)
    spacing = span / count
    bar = spacing * rng.uniform(0.38, 0.55)
    pos = 0.0
    while pos < span:
        if vertical:
            canvas.fill_rect(
                Rect(rect.x0 + pos, rect.y0, rect.x0 + pos + bar, rect.y1),
                stripe,
            )
        else:
            canvas.fill_rect(
                Rect(rect.x0, rect.y0 + pos, rect.x1, rect.y0 + pos + bar),
                stripe,
            )
        pos += spacing


TEXTURES: list[Callable[..., None]] = [
    _draw_colored_checker,
    _draw_dot_texture,
    lambda c, r, a, b, rng: _draw_stripe_texture(c, r, a, b, rng, vertical=True),
    lambda c, r, a, b, rng: _draw_stripe_texture(c, r, a, b, rng, vertical=False),
]


def _pick_accent(palette: dict[str, object], rng: random.Random) -> tuple[int, int, int]:
    accents = palette["accents"]
    assert isinstance(accents, list)
    return rng.choice(accents)


def _compose_eye_grid(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    cols = rng.choice([2, 3])
    rows = rng.choice([2, 3])
    accents = palette["accents"]
    assert isinstance(accents, list)
    pad_x = width * 0.12
    pad_y = height * 0.12
    cell_w = (width - pad_x * 2) / cols
    cell_h = (height - pad_y * 2) / rows
    eye_size = min(cell_w, cell_h) * rng.uniform(0.72, 0.88)
    for row in range(rows):
        iris = accents[row % len(accents)]
        assert isinstance(iris, tuple)
        for col in range(cols):
            cx = pad_x + cell_w * (col + 0.5)
            cy = pad_y + cell_h * (row + 0.5)
            _draw_eye(canvas, cx, cy, eye_size, iris=iris)


def _compose_eye_column(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    iris = _pick_accent(palette, rng)
    count = rng.randint(3, 5)
    eye_size = width * rng.uniform(0.42, 0.58)
    spacing = height / count
    for i in range(count):
        cy = spacing * (i + 0.5)
        _draw_eye(canvas, width / 2, cy, eye_size, iris=iris)


def _compose_starburst_solo(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    cx, cy = width / 2, height / 2
    radius = min(width, height) * rng.uniform(0.28, 0.38)
    points = rng.choice([8, 10, 12, 14])
    color = _pick_accent(palette, rng)
    _draw_starburst(canvas, cx, cy, radius, color, points)


def _compose_star_eye_shadow(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    cx, cy = width / 2, height / 2
    radius = min(width, height) * rng.uniform(0.22, 0.32)
    points = rng.choice([10, 12, 14])
    star_color = _pick_accent(palette, rng)
    shadow_color = _pick_accent(palette, rng)
    while shadow_color == star_color:
        shadow_color = _pick_accent(palette, rng)
    star_pts = _star_points(cx, cy, radius, radius * 0.42, points)
    shadow_len = radius * rng.uniform(1.1, 1.6)
    angle = rng.uniform(math.pi / 5, math.pi / 3)
    _draw_long_shadow(canvas, star_pts, shadow_color, shadow_len, angle)
    _draw_starburst(canvas, cx, cy, radius, star_color, points)
    iris = _pick_accent(palette, rng)
    _draw_eye(canvas, cx, cy, radius * 1.05, iris=iris)


def _compose_triangle_solo(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    cx, cy = width / 2, height / 2
    size = min(width, height) * rng.uniform(0.42, 0.58)
    pointing_up = rng.random() < 0.5
    color = rng.choice([WHITE, _pick_accent(palette, rng)])
    canvas.fill_polygon(_triangle_points(cx, cy, size, pointing_up), color)


def _compose_checker_center(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    accents = palette["accents"]
    assert isinstance(accents, list)
    color_a = accents[0]
    color_b = accents[1] if len(accents) > 1 else BLACK
    assert isinstance(color_a, tuple) and isinstance(color_b, tuple)
    _draw_colored_checker(canvas, Rect(0, 0, width, height), color_a, color_b, rng)
    if rng.random() < 0.55:
        cx, cy = width / 2, height / 2
        eye_size = min(width, height) * rng.uniform(0.28, 0.4)
        iris = _pick_accent(palette, rng)
        _draw_eye(canvas, cx, cy, eye_size, iris=iris)
    else:
        cx, cy = width / 2, height / 2
        radius = min(width, height) * rng.uniform(0.18, 0.28)
        color = WHITE if rng.random() < 0.5 else _pick_accent(palette, rng)
        _draw_starburst(canvas, cx, cy, radius, color, rng.choice([10, 12]))


def _compose_mixed(
    canvas: Canvas,
    width: int,
    height: int,
    palette: dict[str, object],
    rng: random.Random,
) -> None:
    texture = rng.choice(TEXTURES)
    accents = palette["accents"]
    assert isinstance(accents, list)
    color_a = accents[0]
    color_b = accents[rng.randint(1, len(accents) - 1)] if len(accents) > 1 else WHITE
    assert isinstance(color_a, tuple) and isinstance(color_b, tuple)
    texture(canvas, Rect(0, 0, width, height), color_a, color_b, rng)

    placements = rng.randint(2, 5)
    scale = min(width, height)
    for _ in range(placements):
        kind = rng.choice(["eye", "star", "triangle"])
        cx = rng.uniform(scale * 0.15, width - scale * 0.15)
        cy = rng.uniform(scale * 0.15, height - scale * 0.15)
        if kind == "eye":
            _draw_eye(canvas, cx, cy, scale * rng.uniform(0.18, 0.32), iris=_pick_accent(palette, rng))
        elif kind == "star":
            _draw_starburst(
                canvas,
                cx,
                cy,
                scale * rng.uniform(0.1, 0.2),
                _pick_accent(palette, rng),
                rng.choice([8, 10, 12]),
            )
        else:
            canvas.fill_polygon(
                _triangle_points(cx, cy, scale * rng.uniform(0.14, 0.24), rng.random() < 0.5),
                rng.choice([WHITE, _pick_accent(palette, rng)]),
            )


_COMPOSERS: dict[str, Callable[..., None]] = {
    "eye_grid": _compose_eye_grid,
    "eye_column": _compose_eye_column,
    "starburst_solo": _compose_starburst_solo,
    "star_eye_shadow": _compose_star_eye_shadow,
    "triangle_solo": _compose_triangle_solo,
    "checker_center": _compose_checker_center,
    "mixed": _compose_mixed,
}


def generate_rasanova(
    *,
    width: int = 2400,
    height: int = 2400,
    composition: str | None = None,
    bg: tuple[int, int, int] | None = None,
    rng: random.Random,
) -> Canvas:
    palette = rng.choice(PALETTES)
    palette_bg = palette["bg"]
    assert isinstance(palette_bg, tuple)
    background = bg if bg is not None else palette_bg
    assert_not_tan(background, context="rasanova background")

    composition = composition if composition is not None else rng.choice(COMPOSITIONS)
    if composition not in _COMPOSERS:
        raise ValueError(f"Unknown composition: {composition}. Choose from {', '.join(COMPOSITIONS)}")

    canvas = Canvas(width, height, background)
    _COMPOSERS[composition](canvas, width, height, palette, rng)
    return canvas
