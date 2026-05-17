# video-looper

Loops a short 1:1 video clip over a song and exports a finished MP4 for YouTube or Instagram — with a reactive audio waveform visualizer and a canvas color sampled from the video.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install moviepy Pillow
```

## Usage

```bash
.venv/bin/python3 loop_video.py
```

The script will prompt you for two choices:

1. **Audio file** — lists everything in `audio/`
2. **Destination** — YouTube or Instagram

## Project structure

```
video-looper/
├── audio/        # Drop .mp3 / .wav / .aac / .m4a files here
├── video/        # Drop 1:1 video loops here (.mp4 / .mov / .webm)
├── output/       # Rendered files land here
└── loop_video.py
```

## What it does

1. Prompts for an audio file and destination (YouTube or Instagram)
2. Picks a random video loop from `video/`
3. Samples a random pixel from the video to use as the canvas background color
4. **YouTube** — loops the video over the full song at 1920×1080 (16:9)
5. **Instagram** — selects a random 60-second window from the audio and loops the video at 1080×1920 (9:16)
6. Renders a white waveform visualizer below the video that reacts to the audio in real time
7. Exports via H.264 / AAC to `output/` with a timestamp and platform label in the filename

## Output naming

```
output/Song Name_YT_20260517_143022.mp4
output/Song Name_INSTA_20260517_143022.mp4
```
