# video-looper

Generates unique brand-palette artwork for a song, animates three stills with camera motion synced to audio, and exports a 9:16 MP4 for Instagram / YouTube Shorts — with a pulsing border and RasaNova logo.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
brew install cairo   # required by cairosvg (logo)
```

Needs **FFmpeg** on your PATH (MoviePy).

## Input

Drop songs in `audio/`:

- Formats: `.mp3`, `.wav`, `.aac`, `.m4a`
- Media files are gitignored — keep them local only

There is no `video/` source folder. Artwork is generated per song.

## Usage

**Single song (interactive picker):**

```bash
.venv/bin/python3 loop_video.py
```

**Batch (every file in `audio/`):**

```bash
.venv/bin/python3 video_bus.py
```

Each song gets one Shorts MP4 in `output/`. Re-running the same filename reuses the same seed (same style + variants); the audio window and canvas color can still vary unless you pin them in code.

## What it does

1. Derives a **deterministic seed** from the song filename
2. Picks **one generator** and renders **3 variants** of that style
3. Generates oversized square stills on the RasaNova brand palette
4. Takes a **random 60s** window of the song
5. Camera-animates stills (zoom/pan + RMS brightness/saturation), **cycling 1→2→3→1…** with **~0.75s dissolves** every ~4s
6. Composites solid canvas fill (color sampled from the stills — never Tan), art panel, **pulsing white border**, and **RasaNova logo** top-left
7. Exports `1080×1920` Shorts MP4 @ 24fps

## Brand palette

| Name | Hex | Notes |
|------|-----|--------|
| Red | `#E04447` | |
| Orange | `#FCAC0B` | |
| Yellow | `#F5CD26` | |
| Green | `#62AF4E` | |
| Blue | `#009EE0` | |
| Purple | `#9747FF` | |
| Pink | `#FA90B6` | |
| Slate | `#1E1E1E` | Background candidate |
| White | `#FFFFFF` | Background / fill candidate |
| Tan | `#F0E6D0` | **Eye sclera only** — never image bg, fills, or video canvas |

## Generators

| Name | Description |
|------|-------------|
| `kaleidoscope` | 4-fold mirror triangle grid |
| `kalenova` | Kaleidoscope × rasanova motifs |
| `rasanova` | Flat pop-art eyes, stars, textures |
| `mosaic` | Geometric mosaic cell grid |
| `mosaova` | Mosaic grid × rasanova eyes/starbursts |

## Project structure

```
video-looper/
├── assets/           # RasaNova logo (SVG)
├── audio/            # Input songs (gitignored media)
├── art/              # Generators + brand palette
│   ├── palette.py    # Colors + Tan-reserved rule
│   ├── stills.py     # Seed → style → 3 variants
│   └── generators/
├── output/           # Exported MP4s (gitignored)
├── visualizers.py    # Camera-on-still, border, dissolves
├── layout.py         # 9:16 canvas, art scale, logo
├── render.py         # Shorts pipeline
├── loop_video.py     # Interactive CLI
└── video_bus.py      # Batch CLI
```

## Output

```
output/Song Name_SHORTS_YYYYMMDD_HHMMSS.mp4
```

- Size: `1080×1920` (9:16)
- Duration: up to 60 seconds
- Layers: canvas → cycling art → pulsing border → logo
