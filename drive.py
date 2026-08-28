"""Google Drive session scan + on-demand audio download (local GUI only).

Uses the same public folder and Drive v3 queries as the band site.
API key from ``PUBLIC_GOOGLE_API_KEY`` (optional local ``.env``). Never commit a key.
Requests send Referer ``https://rasanova-band.web.app/`` because the site key
is HTTP-referrer restricted.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from session_date import format_song_date
from song_queue import title_from_filename

DRIVE_ROOT_ID = "1n3PMQwCVkMNiBo6FagsmjImJPNUovuhc"
DRIVE_REFERER = "https://rasanova-band.web.app/"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
ENV_KEY = "PUBLIC_GOOGLE_API_KEY"


def load_local_env(path: str = ".env") -> None:
    """Load KEY=VALUE from ``.env`` without overriding a real environment."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def api_key() -> str:
    load_local_env()
    return (os.environ.get(ENV_KEY) or "").strip()


def _request_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Referer": DRIVE_REFERER,
            "User-Agent": "video-looper-local",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(_drive_error(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Drive request failed: {exc.reason}") from exc
    if payload.get("error"):
        raise RuntimeError(_drive_error(payload["error"].get("code"), payload))
    return payload


def _drive_error(code: int | None, detail: object) -> str:
    text = str(detail)
    if code == 403 or "referer" in text.lower() or "referrer" in text.lower():
        return (
            "Drive API key blocked (HTTP referrer). "
            f"Requests use Referer {DRIVE_REFERER}. "
            f"Set {ENV_KEY} in .env to a key allowed for that referrer."
        )
    if not api_key():
        return f"Missing API key — set {ENV_KEY} in .env for local Drive scan."
    return f"Drive API request failed: {text[:400]}"


def _list_files(query: str) -> list[dict]:
    key = api_key()
    if not key:
        raise RuntimeError(f"Missing API key — set {ENV_KEY} in .env for local Drive scan.")
    files: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": query,
            "key": key,
            "fields": "nextPageToken,files(id,name,createdTime,mimeType)",
            "pageSize": "1000",
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{DRIVE_FILES_URL}?{urllib.parse.urlencode(params)}"
        payload = _request_json(url)
        files.extend(payload.get("files") or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return files


def list_session_tracks(root_id: str = DRIVE_ROOT_ID) -> list[dict]:
    """All audio files under session subfolders (no download).

    Each row: file, session, driveId, createdTime, title, date.
    """
    folders = _list_files(
        f"'{root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    folders.sort(key=lambda f: f.get("createdTime") or "", reverse=True)
    tracks: list[dict] = []
    for folder in folders:
        session = folder.get("name") or ""
        audio_files = _list_files(
            f"'{folder['id']}' in parents and mimeType contains 'audio' and trashed = false"
        )
        for f in audio_files:
            filename = f.get("name") or ""
            tracks.append(
                {
                    "file": filename,
                    "session": session,
                    "driveId": f.get("id") or "",
                    "createdTime": f.get("createdTime") or folder.get("createdTime") or "",
                    "title": title_from_filename(filename),
                    "date": format_song_date(None, session or filename),
                }
            )
    return tracks


def download_file(drive_id: str, dest_path: str) -> str:
    """Download one Drive file to ``dest_path``. Skip if it already exists."""
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
        return dest_path
    key = api_key()
    if not key:
        raise RuntimeError(f"Missing API key — set {ENV_KEY} in .env to download audio.")
    if not drive_id:
        raise RuntimeError(f"No Drive id — cannot download {dest_path}")
    params = {"alt": "media", "key": key}
    url = f"{DRIVE_FILES_URL}/{urllib.parse.quote(drive_id)}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Referer": DRIVE_REFERER,
            "User-Agent": "video-looper-local",
        },
    )
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    tmp = f"{dest_path}.part"
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
        os.replace(tmp, dest_path)
    except urllib.error.HTTPError as exc:
        if os.path.isfile(tmp):
            os.remove(tmp)
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(_drive_error(exc.code, detail)) from exc
    except Exception:
        if os.path.isfile(tmp):
            os.remove(tmp)
        raise
    return dest_path
