from __future__ import annotations

import random


def make_rng(seed: int | None = None) -> tuple[random.Random, int]:
    resolved = random.SystemRandom().randrange(1_000_000_000) if seed is None else seed
    return random.Random(resolved), resolved
