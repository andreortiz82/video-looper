from art.generators.kaleidoscope import generate_kaleidoscope
from art.generators.kalenova import generate_kalenova
from art.generators.mosaic import generate_mosaic
from art.generators.mosaova import generate_mosaova
from art.generators.rasanova import generate_rasanova
from art.generators.spiral import generate_spiral

GENERATORS = {
    "kaleidoscope": generate_kaleidoscope,
    "kalenova": generate_kalenova,
    "rasanova": generate_rasanova,
    "mosaic": generate_mosaic,
    "mosaova": generate_mosaova,
    "spiral": generate_spiral,
}

__all__ = [
    "GENERATORS",
    "generate_kaleidoscope",
    "generate_kalenova",
    "generate_mosaic",
    "generate_mosaova",
    "generate_rasanova",
    "generate_spiral",
]
