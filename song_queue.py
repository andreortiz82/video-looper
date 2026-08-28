"""Local Instagram/video queue JSON for the Streamlit GUI.

Live file is ``queue.json`` (gitignored). If that is missing, a leftover
``instagram-queue.json`` is read once and rewritten to ``queue.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from session_date import format_song_date, strip_session_date

QUEUE_PATH = "queue.json"
LEGACY_QUEUE_PATH = "instagram-queue.json"
AUDIO_DIR = "audio"

STATUS_QUEUED = "queued"
STATUS_PREVIEWED = "previewed"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUSES = (STATUS_QUEUED, STATUS_PREVIEWED, STATUS_DONE, STATUS_FAILED)

DEFAULT_STYLE = "a"
DEFAULT_ASPECT = "portrait"
DEFAULT_DURATION = 60.0

QUEUE_FIELDS = (
    "title",
    "file",
    "session",
    "driveId",
    "status",
    "position",
    "style",
    "aspect",
    "seed",
    "date",
    "start",
    "duration",
    "clip_seed",
)


def title_from_filename(name: str) -> str:
    """Unique-title key: strip extension, leading track numbers, session date."""
    stem = os.path.splitext(os.path.basename(name or ""))[0].strip()
    parts = stem.split(" - ", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        stem = parts[1].strip()
    stripped = strip_session_date(stem)
    return stripped or stem


def _title_key(title: str) -> str:
    return " ".join((title or "").casefold().split())


def seed_from_title(title: str) -> int:
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def audio_path(item: dict) -> str:
    """Local path: ``audio/<session>/<file>`` when a session folder is set."""
    filename = item.get("file") or ""
    session = (item.get("session") or "").strip()
    if session:
        return os.path.join(AUDIO_DIR, session, filename)
    return os.path.join(AUDIO_DIR, filename)


def status_after_preview(status: str | None) -> str:
    """Preview never marks done — only previewed (or leaves done alone)."""
    if status == STATUS_DONE:
        return STATUS_DONE
    return STATUS_PREVIEWED


def style_letter(value: Any, fallback: str = DEFAULT_STYLE) -> str:
    letter = str(value or fallback).strip().lower()
    return letter if letter in ("a", "b", "c") else fallback


def start_or_none(value: Any) -> float | None:
    """Empty or 0 → None so render uses the seeded window, not an explicit in-point."""
    if value is None or value == "":
        return None
    start = _as_float(value)
    if start is None or start == 0:
        return None
    return start


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_item(raw: dict | None, position: int) -> dict:
    raw = raw or {}
    filename = raw.get("file") or raw.get("filename") or ""
    title = (raw.get("title") or "").strip() or title_from_filename(filename)
    session = (raw.get("session") or "").strip()
    drive_id = raw.get("driveId") or raw.get("drive_id") or ""
    status = raw.get("status") or STATUS_QUEUED
    if status not in STATUSES:
        status = STATUS_QUEUED
    style = (raw.get("style") or DEFAULT_STYLE).strip().lower()
    if style not in ("a", "b", "c"):
        style = DEFAULT_STYLE
    aspect = raw.get("aspect") or DEFAULT_ASPECT
    seed = _as_int(raw.get("seed"))
    if seed is None:
        seed = seed_from_title(title or filename)
    date = (raw.get("date") or "").strip()
    if not date:
        date = format_song_date(audio_path({"file": filename, "session": session}), session or None)
    duration = _as_float(raw.get("duration"))
    if duration is None or duration <= 0:
        duration = DEFAULT_DURATION
    return {
        "title": title,
        "file": filename,
        "session": session,
        "driveId": str(drive_id) if drive_id else "",
        "status": status,
        "position": int(raw["position"]) if raw.get("position") is not None else position,
        "style": style,
        "aspect": aspect,
        "seed": seed,
        "date": date,
        "start": _as_float(raw.get("start")),
        "duration": duration,
        "clip_seed": _as_int(raw.get("clip_seed")),
    }


def _items_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("items", "queue", "songs"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def load_queue(path: str | None = None) -> dict:
    """Return ``{"items": [...]}`` sorted by position, gaps filled."""
    chosen = path
    if chosen is None:
        if os.path.isfile(QUEUE_PATH):
            chosen = QUEUE_PATH
        elif os.path.isfile(LEGACY_QUEUE_PATH):
            chosen = LEGACY_QUEUE_PATH
        else:
            return {"items": []}
    with open(chosen, encoding="utf-8") as f:
        payload = json.load(f)
    items = [
        normalize_item(raw, i) for i, raw in enumerate(_items_from_payload(payload))
    ]
    items.sort(key=lambda it: it.get("position", 0))
    for i, item in enumerate(items):
        item["position"] = i
    return {"items": items}


def save_queue(queue: dict, path: str = QUEUE_PATH) -> None:
    items = list(queue.get("items") or [])
    for i, item in enumerate(items):
        item["position"] = i
    payload = {"items": [{k: item.get(k) for k in QUEUE_FIELDS} for item in items]}
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def newest_take_per_title(tracks: list[dict]) -> list[dict]:
    """Keep one row per title — the take with the latest ``createdTime``."""
    best: dict[str, dict] = {}
    for track in tracks:
        title = track.get("title") or title_from_filename(track.get("file") or "")
        key = _title_key(title)
        if not key:
            continue
        row = dict(track)
        row["title"] = title
        prev = best.get(key)
        if prev is None or (row.get("createdTime") or "") > (prev.get("createdTime") or ""):
            best[key] = row
    return list(best.values())


def append_unseen(items: list[dict], takes: list[dict]) -> tuple[list[dict], int]:
    """Append unseen titles without changing existing order.

    Skips driveIds already in the queue and titles already present
    (case-insensitive). New rows are queued at the end.
    """
    existing = [dict(it) for it in items]
    seen_ids = {it.get("driveId") for it in existing if it.get("driveId")}
    seen_titles = {_title_key(it.get("title") or "") for it in existing}
    added = 0
    for take in takes:
        drive_id = take.get("driveId") or ""
        title = take.get("title") or title_from_filename(take.get("file") or "")
        if drive_id and drive_id in seen_ids:
            continue
        if _title_key(title) in seen_titles:
            continue
        item = normalize_item(
            {
                "title": title,
                "file": take.get("file") or "",
                "session": take.get("session") or "",
                "driveId": drive_id,
                "status": STATUS_QUEUED,
                "style": DEFAULT_STYLE,
                "aspect": DEFAULT_ASPECT,
                "seed": seed_from_title(title),
                "date": take.get("date") or "",
                "start": None,
                "duration": DEFAULT_DURATION,
                "clip_seed": None,
            },
            len(existing),
        )
        existing.append(item)
        added += 1
        if drive_id:
            seen_ids.add(drive_id)
        seen_titles.add(_title_key(title))
    for i, item in enumerate(existing):
        item["position"] = i
    return existing, added
