# video-looper

Generates unique brand-palette Shorts for a song — explore **Style A**, **Style B**, or the classic camera-on-still layout.

Branch `explore/style-ab-layouts` adds Now Playing card layouts with generated covers and animated backgrounds.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
brew install cairo   # required by cairosvg (logo + covers)
```

Needs **FFmpeg** on your PATH (MoviePy).

## Input

Drop songs in `audio/`:

- Formats: `.mp3`, `.wav`, `.aac`, `.m4a`
- Media files are gitignored — keep them local only

There is no `video/` source folder. Artwork is generated per song.

## Usage

**Single song (interactive picker — song + layout):**

```bash
.venv/bin/python3 loop_video.py
```

**Batch (every file in `audio/`):**

```bash
.venv/bin/python3 video_bus.py          # classic
.venv/bin/python3 video_bus.py a        # Style A
.venv/bin/python3 video_bus.py b        # Style B
```

## Layout styles

| Style | Background | Chrome |
|-------|------------|--------|
| **A** | Off-center wavy spiral, full-bleed, rotates 360° | Centered logo + Now Playing card (cover over title/date); pulsing randomized border |
| **B** | Mosaic on brand palette, RMS brightness/sat pulse | Now Playing card: large logo on random accent + cover/meta row; pulsing randomized border |
| **Classic** | Solid canvas sampled from stills | Camera-on-still panel × 3 variants, top-left logo, white pulsing border |

Covers are recolored from `assets/covers/base/*.svg` (vendored from rasanova). **Tan `#F0E6D0` is eye sclera only** — locked on eye tiles, remapped away on everything else.

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
| `mosaic` | Geometric mosaic cell grid (Style B bg) |
| `mosaova` | Mosaic grid × rasanova eyes/starbursts |
| `spiral` | Wavy nested-square spiral (Style A bg; not used in classic still cycle) |

## Project structure

```
video-looper/
├── assets/
│   ├── rasanova-logo.svg
│   └── covers/base/      # SVG cover templates
├── audio/                # Input songs (gitignored media)
├── art/
│   ├── palette.py
│   ├── covers.py         # SVG recolor + rasterize
│   ├── stills.py
│   └── generators/       # spiral, mosaic, …
├── chrome.py             # Now Playing cards + logo
├── visualizers.py
├── layout.py             # Classic geometry
├── render.py
├── loop_video.py
└── video_bus.py
```

## Output

```
output/Song Name_SHORTS_STYLE_A_YYYYMMDD_HHMMSS.mp4
output/Song Name_SHORTS_STYLE_B_YYYYMMDD_HHMMSS.mp4
output/Song Name_SHORTS_YYYYMMDD_HHMMSS.mp4          # classic
```

- Size: `1080×1920` (9:16)
- Duration: up to 60 seconds
