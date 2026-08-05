"""Randomized cover artifacts from SVG bases.

Recolor rules mirror rasanova/src/scripts/mosaic-tile.ts:
- Eye tiles: Tan path fills stay Tan (sclera); Slate path fills stay Slate (pupils).
- All other fills remap to brand accents.
- Tan is never used as a background or non-eye fill.
"""

from __future__ import annotations

import io
import os
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

try:
    import cairosvg
except OSError as exc:
    raise SystemExit(
        "cairosvg requires the Cairo system library. Install with: brew install cairo"
    ) from exc

from PIL import Image

from art.palette import ACCENTS, SLATE, TAN, assert_not_tan, is_tan

COVERS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "covers", "base")
)

BASE_COVER_FILES = [
    "eye.svg",
    "star.svg",
    "eye-star.svg",
    "triangle.svg",
    "checkers.svg",
    "eyes-stack.svg",
    "eyes-grid.svg",
    "archway.svg",
]

EYE_COVERS = frozenset(
    {
        "eye.svg",
        "eye-star.svg",
        "eyes-stack.svg",
        "eyes-grid.svg",
    }
)

_HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")
_NS = {"svg": "http://www.w3.org/2000/svg"}


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _normalize_hex(value: str | None) -> str | None:
    if not value:
        return None
    m = _HEX_RE.match(value.strip())
    return f"#{m.group(1).upper()}" if m else None


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    return tag.lower()


def _inside_clip_path(el: ET.Element, parents: dict[ET.Element, ET.Element | None]) -> bool:
    cur = parents.get(el)
    while cur is not None:
        if _local_tag(cur.tag) == "clippath":
            return True
        cur = parents.get(cur)
    return False


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element | None]:
    parents: dict[ET.Element, ET.Element | None] = {root: None}
    stack = [root]
    while stack:
        node = stack.pop()
        for child in list(node):
            parents[child] = node
            stack.append(child)
    return parents


def _accent_hexes(rng: random.Random) -> list[str]:
    accents = list(ACCENTS)
    rng.shuffle(accents)
    return [_rgb_to_hex(c) for c in accents]


def recolor_cover_svg(svg_markup: str, filename: str, rng: random.Random) -> str:
    """Return recolored SVG markup. Tan locked to eye sclera on eye tiles only."""
    # ElementTree needs a default namespace stripped for simpler queries.
    markup = re.sub(r'\sxmlns="[^"]+"', "", svg_markup, count=1)
    root = ET.fromstring(markup)
    parents = _build_parent_map(root)
    lock_eyes = filename in EYE_COVERS
    tan_hex = _rgb_to_hex(TAN)
    slate_hex = _rgb_to_hex(SLATE)

    nodes: list[tuple[ET.Element, str, bool]] = []
    unlocked: list[str] = []

    for el in root.iter():
        if _inside_clip_path(el, parents):
            continue
        hex_val = _normalize_hex(el.get("fill"))
        if not hex_val:
            continue
        tag = _local_tag(el.tag)
        lock = False
        if lock_eyes:
            if hex_val == tan_hex and tag == "path":
                lock = True
            elif hex_val == slate_hex and tag == "path":
                lock = True
        nodes.append((el, hex_val, lock))
        if not lock and hex_val not in unlocked:
            unlocked.append(hex_val)

    targets = _accent_hexes(rng)
    while len(targets) < len(unlocked):
        targets.extend(_accent_hexes(rng))

    mapping = {hex_val: targets[i] for i, hex_val in enumerate(unlocked)}

    for el, hex_val, lock in nodes:
        if lock:
            el.set("fill", tan_hex if hex_val == tan_hex else slate_hex)
        else:
            new_hex = mapping.get(hex_val, rng.choice(targets))
            rgb = _hex_to_rgb(new_hex)
            assert_not_tan(rgb, context=f"cover fill ({filename})")
            el.set("fill", new_hex)

    # Restore SVG namespace for cairosvg friendliness.
    root.set("xmlns", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


@dataclass(frozen=True)
class CoverResult:
    filename: str
    image: Image.Image
    svg: str


def load_base_svg(filename: str) -> str:
    path = os.path.join(COVERS_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def generate_cover(
    rng: random.Random,
    *,
    size: int = 800,
    filename: str | None = None,
) -> CoverResult:
    """Pick a base SVG, recolor, and rasterize to a square PIL image."""
    name = filename or rng.choice(BASE_COVER_FILES)
    raw = load_base_svg(name)
    recolored = recolor_cover_svg(raw, name, rng)
    png = cairosvg.svg2png(bytestring=recolored.encode("utf-8"), output_width=size, output_height=size)
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    # Flatten onto non-Tan opaque square if SVG had transparency.
    bg = Image.new("RGBA", image.size, (30, 30, 30, 255))
    composed = Image.alpha_composite(bg, image).convert("RGB")
    # Guard: cover canvas pixels must not be all-Tan (sclera-only rule for bgs).
    sample = composed.getpixel((size // 2, 4))
    if is_tan(sample) and name not in EYE_COVERS:
        assert_not_tan(sample, context="cover background")
    return CoverResult(filename=name, image=composed, svg=recolored)
