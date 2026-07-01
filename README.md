# video-looper

Loops a short 1:1 video clip over a song and exports a finished MP4 for YouTube or Instagram — with a reactive radial background, pulsing border, and RasaNova logo.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
brew install cairo   # required by cairosvg
```

## Usage

**Single file (interactive):**

```bash
.venv/bin/python3 loop_video.py
```

**Batch (all files in `audio/`):**

```bash
.venv/bin/python3 video_bus.py --dest insta
```

## Project structure

```
video-looper/
├── assets/           # RasaNova logo (SVG)
├── audio/
├── video/
├── output/
├── visualizers.py    # Radial background, pulsing border
├── layout.py         # Video scale, fixed logo placement
├── render.py         # Unified render pipeline
├── loop_video.py
└── video_bus.py
```

## What it does

1. Picks a random video loop and samples two random colors from it (background + radial spokes)
2. Renders a **radial** audio-reactive background centered behind the video
3. Scales the loop on canvas (72% width Instagram, 58% height YouTube)
4. Always shows **pulsing white border** around the video
5. Always places **RasaNova logo** top-left
6. **Instagram** — random 60s window at 1080×1920
7. **YouTube** — full song at 1920×1080

## Visual layers

| Layer | Description |
|-------|-------------|
| Radial background | Solid fill + 72 FFT-driven spokes; colors sampled from the video loop |
| Pulsing border | White outline around the video; thickness follows RMS |
| Video loop | Scaled 1:1 clip, centered |
| Logo | RasaNova mark, fixed top-left |

## Output naming

```
output/Song Name_YT_20260517_143022.mp4
output/Song Name_INSTA_20260517_143022.mp4
```
