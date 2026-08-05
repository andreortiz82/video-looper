"""Song-seeded still generation for Shorts."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from PIL import Image

from art.generators import GENERATORS
from art.rng import make_rng

STILL_SIZE = 1600
GENERATOR_NAMES = list(GENERATORS.keys())
STILLS_PER_SONG = 3


@dataclass(frozen=True)
class StillResult:
    name: str
    seed: int
    image: Image.Image


def seed_from_song(song_name: str) -> int:
    digest = hashlib.sha256(song_name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _pick_style(master_seed: int) -> str:
    rng = random.Random(master_seed)
    return rng.choice(GENERATOR_NAMES)


def generate_stills(
    song_name: str,
    *,
    master_seed: int | None = None,
    size: int = STILL_SIZE,
) -> list[StillResult]:
    """Pick one style from the seed, then render STILLS_PER_SONG variants."""
    seed = master_seed if master_seed is not None else seed_from_song(song_name)
    style = _pick_style(seed)
    results: list[StillResult] = []

    print(f"  Style: {style}")
    for i in range(STILLS_PER_SONG):
        derived = seed + i + 1
        rng, _ = make_rng(derived)
        canvas = GENERATORS[style](width=size, height=size, rng=rng)
        results.append(StillResult(name=style, seed=derived, image=canvas.image.copy()))
        print(f"  Still {i + 1}/{STILLS_PER_SONG}: {style} (seed={derived})")

    return results
