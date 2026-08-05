from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def lerp(self, other: Point, t: float) -> Point:
        return Point(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> Point:
        return Point((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def inset(self, margin: float) -> Rect:
        return Rect(self.x0 + margin, self.y0 + margin, self.x1 - margin, self.y1 - margin)

    def as_int_tuple(self) -> tuple[int, int, int, int]:
        return (int(self.x0), int(self.y0), int(self.x1), int(self.y1))


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lower()
    named = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
    }
    if value in named:
        return named[value]
    if value.startswith("#") and len(value) == 7:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    raise ValueError(f"Unsupported color: {value}")


class Canvas:
    def __init__(
        self,
        width: int,
        height: int,
        background: tuple[int, int, int],
    ) -> None:
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), background)
        self.draw = ImageDraw.Draw(self.image)

    @classmethod
    def square(cls, size: int, background: tuple[int, int, int]) -> Canvas:
        return cls(size, size, background)

    def save(self, path: str) -> None:
        self.image.save(path, format="PNG")

    def draw_line(
        self,
        start: Point,
        end: Point,
        color: tuple[int, int, int],
        width: int = 1,
        jitter: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        if jitter and rng:
            start = Point(
                start.x + rng.uniform(-jitter, jitter),
                start.y + rng.uniform(-jitter, jitter),
            )
            end = Point(
                end.x + rng.uniform(-jitter, jitter),
                end.y + rng.uniform(-jitter, jitter),
            )
        self.draw.line(
            [(start.x, start.y), (end.x, end.y)],
            fill=color,
            width=width,
        )

    def fill_polygon(
        self,
        points: Sequence[Point],
        fill: tuple[int, int, int],
    ) -> None:
        if len(points) < 3:
            return
        self.draw.polygon([(p.x, p.y) for p in points], fill=fill)

    def draw_polygon(
        self,
        points: Sequence[Point],
        color: tuple[int, int, int],
        width: int = 1,
    ) -> None:
        if len(points) < 2:
            return
        coords = [(p.x, p.y) for p in points] + [(points[0].x, points[0].y)]
        self.draw.line(coords, fill=color, width=width)

    def fill_rect(self, rect: Rect, color: tuple[int, int, int]) -> None:
        self.draw.rectangle(rect.as_int_tuple(), fill=color)

    def draw_ellipse(
        self,
        rect: Rect,
        outline: tuple[int, int, int] | None = None,
        fill: tuple[int, int, int] | None = None,
        width: int = 1,
    ) -> None:
        self.draw.ellipse(rect.as_int_tuple(), outline=outline, fill=fill, width=width)

    def clip_rect(self, rect: Rect) -> Image.Image:
        return self.image.crop(rect.as_int_tuple())

    def paste(self, patch: Image.Image, rect: Rect) -> None:
        self.image.paste(patch, rect.as_int_tuple()[:2])

    def with_clip(self, rect: Rect, draw_fn) -> None:
        """Draw into a clipped patch and composite back onto the canvas."""
        patch = Image.new("RGB", (int(rect.width), int(rect.height)), (255, 255, 255))
        patch_draw = ImageDraw.Draw(patch)
        draw_fn(patch, patch_draw, rect)
        self.paste(patch, rect)
