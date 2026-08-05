#!/usr/bin/env bash
# Render Style A and Style B for one song.
# Usage: ./scripts/render_both.sh "04 - Whale Song.wav"
set -euo pipefail
cd "$(dirname "$0")/.."

SONG="${1:-}"
if [[ -z "$SONG" ]]; then
  echo 'Usage: ./scripts/render_both.sh "04 - Whale Song.wav"'
  exit 1
fi

PYTHON="${PYTHON:-.venv/bin/python3}"
"$PYTHON" scripts/render_song.py "$SONG" a
"$PYTHON" scripts/render_song.py "$SONG" b
