# video-looper

Loops a short 1:1 video clip over a song and exports a finished MP4 for YouTube or Instagram — with a reactive audio visualizer and a canvas color sampled from the video.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install moviepy Pillow
```

## Usage

```bash
.venv/bin/python3 loop_video.py
```

The script walks you through four prompts:

1. **Audio file** — lists everything in `audio/`
2. **Destination** — YouTube or Instagram
3. **Visualizers** — comma-separated selection (e.g. `1,3`)

## Project structure

```
video-looper/
├── audio/        # Drop .mp3 / .wav / .aac / .m4a files here
├── video/        # Drop 1:1 video loops here (.mp4 / .mov / .webm)
├── output/       # Rendered files land here
└── loop_video.py
```

## What it does

1. Prompts for an audio file, destination, and visualizer selection
2. Picks a random video loop from `video/`
3. Samples a random pixel from the video to use as the canvas background color
4. **YouTube** — loops the video over the full song at 1920×1080 (16:9)
5. **Instagram** — selects a random 60-second window from the audio and loops the video at 1080×1920 (9:16)
6. Renders the selected visualizer(s) below the video, reacting to the audio in real time
7. Exports via H.264 / AAC to `output/` with a timestamp and platform label in the filename

## Visualizers

| # | Name | Description |
|---|------|-------------|
| 1 | Waveform | White oscillating line — 80ms audio window, normalized to local peak |
| 2 | Frequency bars | 48 log-spaced FFT bars from 40Hz–10kHz, normalized per frame |
| 3 | Pulsing border | Rectangle around the video that grows with RMS amplitude |

Select any combination at the prompt, e.g. `2,3` or `1,2,3` for all three. Defaults to waveform if left blank.

## Output naming

```
output/Song Name_YT_20260517_143022.mp4
output/Song Name_INSTA_20260517_143022.mp4
```
