#!/usr/bin/env python3
"""Local Streamlit GUI for the Rasa Nova Instagram/video queue.

    streamlit run app.py

Local only — no Streamlit Cloud. Queue JSON is queue.json (gitignored).
"""

from __future__ import annotations

import glob
import os
import random
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import streamlit as st

from drive import api_key, download_file, list_session_tracks
from song_queue import (
    STATUS_DONE,
    STATUS_FAILED,
    audio_path,
    append_unseen,
    load_queue,
    newest_take_per_title,
    save_queue,
    status_after_preview,
)

STYLES = ("a", "b", "c")
ASPECT_LABELS = {
    "portrait": "Portrait 9:16",
    "square": "Square 1:1",
    "landscape": "Landscape 16:9",
}


def _item_key(item: dict) -> str:
    return item.get("driveId") or f"pos-{item.get('position', 0)}"


def _ensure_audio(item: dict) -> str:
    path = audio_path(item)
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path
    return download_file(item.get("driveId") or "", path)


def _song_stem(item: dict) -> str:
    return os.path.splitext(os.path.basename(item.get("file") or ""))[0]


def _latest_previews(item: dict) -> list[str]:
    stem = _song_stem(item)
    if not stem:
        return []
    try:
        from layout import aspect_tag

        ar = aspect_tag(item.get("aspect") or "portrait")
    except Exception:
        ar = {"portrait": "9x16", "square": "1x1", "landscape": "16x9"}.get(
            item.get("aspect") or "portrait", "9x16"
        )
    style = (item.get("style") or "a").upper()
    pattern = os.path.join("output", "preview", f"{stem}_{ar}_STYLE_{style}_*.png")
    paths = glob.glob(pattern)
    paths.sort(key=os.path.getmtime, reverse=True)
    return paths[:3]


def _init_widget(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _sync_item_from_widgets(item: dict, iid: str) -> None:
    item["style"] = st.session_state.get(f"style_{iid}", item.get("style") or "a")
    aspect_label = st.session_state.get(f"aspect_{iid}")
    if aspect_label:
        for key, label in ASPECT_LABELS.items():
            if label == aspect_label:
                item["aspect"] = key
                break
    item["seed"] = int(st.session_state.get(f"seed_{iid}", item.get("seed") or 0))
    item["title"] = st.session_state.get(f"title_{iid}", item.get("title") or "")
    item["date"] = st.session_state.get(f"date_{iid}", item.get("date") or "")
    if st.session_state.get(f"set_start_{iid}", item.get("start") is not None):
        item["start"] = float(st.session_state.get(f"start_{iid}", item.get("start") or 0.0))
        item["clip_seed"] = None
    else:
        item["start"] = None
        if st.session_state.get(f"set_clip_{iid}"):
            item["clip_seed"] = int(st.session_state.get(f"clip_seed_{iid}") or 0)
        else:
            item["clip_seed"] = None
    item["duration"] = float(st.session_state.get(f"duration_{iid}", item.get("duration") or 60))


st.set_page_config(page_title="Rasa Nova video queue", layout="wide")
st.title("Rasa Nova video queue")
st.caption("Local only. Preview stills do not mark a song done — full MP4 render can, if you confirm.")

queue = load_queue()
items = queue["items"]

with st.sidebar:
    st.header("Drive")
    if not api_key():
        st.warning("Set `PUBLIC_GOOGLE_API_KEY` in `.env` to scan / download.")
    if st.button("Scan Google Drive", use_container_width=True):
        try:
            with st.spinner("Listing session folders…"):
                tracks = list_session_tracks()
                takes = newest_take_per_title(tracks)
                items, added = append_unseen(items, takes)
                queue["items"] = items
                save_queue(queue)
            st.success(f"Added {added} new song(s). Queue has {len(items)}.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.caption("Appends unseen titles. Existing order stays put. Audio downloads on preview/render.")

if not items:
    st.info("Queue is empty. Scan Google Drive from the sidebar, or add rows to `queue.json`.")
    st.stop()

table_rows = [
    {
        "#": item["position"] + 1,
        "title": item.get("title") or "",
        "status": item.get("status") or "",
        "session": item.get("session") or "",
        "style": (item.get("style") or "").upper(),
        "aspect": item.get("aspect") or "",
        "date": item.get("date") or "",
    }
    for item in items
]
st.dataframe(table_rows, hide_index=True, use_container_width=True)

labels = [f"{it['position'] + 1}. {it.get('title') or '(untitled)'}  ·  {it.get('status')}" for it in items]
selected_idx = st.selectbox(
    "Selected song",
    range(len(items)),
    format_func=lambda i: labels[i],
    key="selected_song",
)
item = items[selected_idx]
iid = _item_key(item)

with st.sidebar:
    st.divider()
    st.header("Selected")
    st.caption(item.get("session") or "No session folder")

    _init_widget(f"style_{iid}", item.get("style") or "a")
    _init_widget(f"aspect_{iid}", ASPECT_LABELS.get(item.get("aspect") or "portrait", ASPECT_LABELS["portrait"]))
    _init_widget(f"seed_{iid}", int(item.get("seed") or 0))
    _init_widget(f"title_{iid}", item.get("title") or "")
    _init_widget(f"date_{iid}", item.get("date") or "")
    _init_widget(f"set_start_{iid}", item.get("start") is not None)
    _init_widget(f"start_{iid}", float(item.get("start") or 0.0))
    _init_widget(f"duration_{iid}", float(item.get("duration") or 60))
    _init_widget(f"set_clip_{iid}", item.get("clip_seed") is not None)
    _init_widget(f"clip_seed_{iid}", int(item.get("clip_seed") or 0))

    st.radio("Style", STYLES, key=f"style_{iid}", format_func=lambda s: s.upper(), horizontal=True)
    st.selectbox("Aspect", list(ASPECT_LABELS.values()), key=f"aspect_{iid}")

    seed_col, roll_col = st.columns([3, 1])
    with seed_col:
        st.number_input("Art seed", step=1, key=f"seed_{iid}")
    with roll_col:
        st.write("")
        if st.button("Reroll", help="New --seed for artwork"):
            st.session_state[f"seed_{iid}"] = random.randint(1, 2_147_483_647)
            _sync_item_from_widgets(item, iid)
            save_queue(queue)
            st.rerun()

    st.text_input("Display name (chrome title)", key=f"title_{iid}")
    st.text_input("Date (chrome)", key=f"date_{iid}", help="Wired to RenderOptions.song_date / session folder date")

    st.checkbox("Set in-point (--start)", key=f"set_start_{iid}")
    st.number_input("Start (seconds)", min_value=0.0, step=0.5, key=f"start_{iid}", disabled=not st.session_state.get(f"set_start_{iid}"))
    st.number_input("Duration (seconds)", min_value=1.0, step=1.0, key=f"duration_{iid}")
    st.checkbox(
        "Set clip seed (--clip-seed)",
        key=f"set_clip_{iid}",
        disabled=bool(st.session_state.get(f"set_start_{iid}")),
        help="Random 60s window seed when in-point is unset",
    )
    st.number_input(
        "Clip seed",
        step=1,
        key=f"clip_seed_{iid}",
        disabled=(
            (not st.session_state.get(f"set_clip_{iid}"))
            or bool(st.session_state.get(f"set_start_{iid}"))
        ),
    )

    _sync_item_from_widgets(item, iid)
    try:
        from layout import normalize_aspect

        item["aspect"] = normalize_aspect(item.get("aspect") or "portrait")
    except Exception:
        item["aspect"] = item.get("aspect") or "portrait"
    save_queue(queue)

    st.divider()
    preview_clicked = st.button("Render preview stills", use_container_width=True)
    mark_done_after = st.checkbox("Mark done if MP4 render succeeds", value=False)
    render_clicked = st.button("Render MP4", use_container_width=True, type="primary")
    if item.get("status") != STATUS_DONE and st.button("Mark done", use_container_width=True):
        item["status"] = STATUS_DONE
        save_queue(queue)
        st.rerun()

if preview_clicked:
    try:
        with st.spinner("Downloading audio if needed, then writing preview PNGs…"):
            song_path = _ensure_audio(item)
            from render import write_layout_previews

            paths = write_layout_previews(
                song_path,
                _song_stem(item),
                master_seed=item.get("seed"),
                song_date=item.get("date") or None,
                display_name=item.get("title") or None,
                aspect=item.get("aspect") or "portrait",
                styles=item.get("style") or "a",
            )
        item["status"] = status_after_preview(item.get("status"))
        save_queue(queue)
        st.success(f"Wrote {len(paths)} preview(s). Status: {item['status']} (not done).")
        st.rerun()
    except Exception as exc:
        item["status"] = STATUS_FAILED
        save_queue(queue)
        st.error(str(exc))

if render_clicked:
    try:
        with st.spinner("Downloading audio if needed, then rendering MP4…"):
            song_path = _ensure_audio(item)
            from render import RenderOptions, render

            out = render(
                song_path,
                _song_stem(item),
                RenderOptions(
                    master_seed=item.get("seed"),
                    layout_style=item.get("style") or "a",
                    aspect=item.get("aspect") or "portrait",
                    song_date=item.get("date") or None,
                    display_name=item.get("title") or None,
                    audio_start=item.get("start"),
                    audio_duration=item.get("duration"),
                    clip_seed=item.get("clip_seed"),
                ),
            )
        if mark_done_after:
            item["status"] = STATUS_DONE
        save_queue(queue)
        st.success(f"Wrote {out}" + (" — marked done." if mark_done_after else " — not marked done."))
        st.session_state["last_mp4"] = out
    except Exception as exc:
        item["status"] = STATUS_FAILED
        save_queue(queue)
        st.error(str(exc))

st.subheader("Preview stills")
previews = _latest_previews(item)
if previews:
    cols = st.columns(len(previews))
    for col, path in zip(cols, previews):
        col.image(path, caption=os.path.basename(path), use_container_width=True)
else:
    st.caption("No stills in `output/preview/` for this song/style/aspect yet.")

if st.session_state.get("last_mp4"):
    st.caption(f"Last MP4: `{st.session_state['last_mp4']}`")
