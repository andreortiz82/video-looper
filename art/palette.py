"""RasaNova brand palette for all Shorts generators.

Rule: Tan (#F0E6D0) is reserved for eye sclera only.
Never use Tan as a canvas/image background, accent fill, or video backdrop.
"""

from __future__ import annotations

RED = (224, 68, 71)        # #E04447
ORANGE = (252, 172, 11)    # #FCAC0B
YELLOW = (245, 205, 38)    # #F5CD26
GREEN = (98, 175, 78)      # #62AF4E
BLUE = (0, 158, 224)       # #009EE0
PURPLE = (151, 71, 255)    # #9747FF
PINK = (250, 144, 182)     # #FA90B6
TAN = (240, 230, 208)      # #F0E6D0 — eye sclera only
SLATE = (30, 30, 30)       # #1E1E1E
WHITE = (255, 255, 255)    # #FFFFFF

# Alias used exclusively as default eye sclera (see rasanova._draw_eye).
EYE_SCLERA = TAN
CREAM = EYE_SCLERA  # backward-compatible name; do not use for fills/backgrounds

ACCENTS: list[tuple[int, int, int]] = [RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK]
# Image / video backgrounds — Tan excluded by design.
BACKGROUNDS: list[tuple[int, int, int]] = [SLATE, WHITE]


def is_tan(color: tuple[int, int, int], tolerance: int = 12) -> bool:
    """True if color is Tan (or close enough to be treated as reserved)."""
    return all(abs(a - b) <= tolerance for a, b in zip(color, TAN))


def assert_not_tan(color: tuple[int, int, int], *, context: str = "color") -> None:
    if is_tan(color):
        raise ValueError(f"{context} must not use Tan (reserved for eye sclera only): {color}")


# Kaleidoscope: (fg, bg) pairs — no Tan
KALEIDOSCOPE_PALETTES: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
    (RED, SLATE),
    (ORANGE, SLATE),
    (YELLOW, SLATE),
    (BLUE, SLATE),
    (PURPLE, WHITE),
    (PINK, WHITE),
    (GREEN, SLATE),
    (SLATE, WHITE),
]

# Mosaic: accent lists (bg separate) — no Tan
MOSAIC_PALETTES: list[list[tuple[int, int, int]]] = [
    [RED, ORANGE, YELLOW, PINK],
    [BLUE, PURPLE, PINK, WHITE],
    [GREEN, YELLOW, ORANGE, BLUE],
    [PURPLE, RED, PINK, WHITE],
    ACCENTS[:],
]

# Rasanova / Kalenova style dicts — no Tan backgrounds or accents
RASANOVA_PALETTES: list[dict[str, object]] = [
    {"bg": SLATE, "accents": [RED, ORANGE, YELLOW, PINK], "secondary": RED},
    {"bg": SLATE, "accents": [BLUE, PURPLE, PINK, GREEN], "secondary": BLUE},
    {"bg": WHITE, "accents": [RED, PURPLE, BLUE, ORANGE], "secondary": PURPLE},
    {"bg": WHITE, "accents": [GREEN, YELLOW, ORANGE, PINK], "secondary": GREEN},
    {"bg": WHITE, "accents": [RED, BLUE, PURPLE, SLATE], "secondary": RED},
    {"bg": SLATE, "accents": ACCENTS[:], "secondary": ORANGE},
]
