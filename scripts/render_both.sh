#!/usr/bin/env bash
# Render Style A, B, and C for one song.
# Extra flags are forwarded to render_song.py (aspect, start, seed, video, …).
#
# Examples:
#   ./scripts/render_both.sh "04 - Whale Song.wav"
#   ./scripts/render_both.sh "Big E.mp3" --aspect square --start 15
#   ./scripts/render_both.sh "04 - Whale Song.wav" --aspect landscape --video clip.mp4
set -euo pipefail
cd "$(dirname "$0")/.."

SONG="${1:-}"
if [[ -z "$SONG" ]]; then
  echo 'Usage: ./scripts/render_both.sh "04 - Whale Song.wav" [--aspect square] [...]'
  exit 1
fi
shift

PYTHON="${PYTHON:-.venv/bin/python3}"
"$PYTHON" scripts/render_song.py "$SONG" a "$@"
"$PYTHON" scripts/render_song.py "$SONG" b "$@"
"$PYTHON" scripts/render_song.py "$SONG" c "$@"
