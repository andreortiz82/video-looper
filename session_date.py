"""Resolve the on-screen chrome date from a session folder / audio filename.

Drive session folders carry the recording date in the name. Fresh downloads
have mtime = download time, so chrome must not use datetime.now() or mtime
when a date can be parsed from the path.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

_MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_MONTH_ALT = "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))

# Month D YYYY | Month Dth YY | glued Jan15 YYYY — extra words allowed.
_DATE_RE = re.compile(
    rf"""
    \b
    (?P<month>{_MONTH_ALT})
    (?:
        [.\-_\s]+
        |
        (?=\d)
    )
    (?P<day>\d{{1,2}})
    (?:st|nd|rd|th)?
    [.\-_\s,]+
    (?P<year>\d{{4}}|\d{{2}})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def format_chrome_date(dt: datetime) -> str:
    """English chrome date: ``May 16, 2026`` (no zero-padded day)."""
    return f"{_MONTH_ABBR[dt.month - 1]} {dt.day}, {dt.year}"


def parse_session_date(text: str | None) -> datetime | None:
    """Extract a calendar date from a folder or file name, if one is present."""
    if not text:
        return None
    for match in _DATE_RE.finditer(text):
        month = _MONTH_NAMES[match.group("month").lower()]
        day = int(match.group("day"))
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            continue
    return None


def strip_session_date(text: str | None) -> str:
    """Remove an embedded session date from a folder or file stem.

    ``A Funny Handshake May 16 2026`` → ``A Funny Handshake``.
    """
    if not text:
        return ""
    match = _DATE_RE.search(text)
    if not match:
        return text.strip()
    cleaned = f"{text[: match.start()]} {text[match.end() :]}"
    return re.sub(r"[\s._\-]+", " ", cleaned).strip(" -_.,")


def _date_from_audio_path(song_path: str) -> datetime | None:
    parent = os.path.basename(os.path.dirname(song_path.rstrip(os.sep)))
    if parent not in ("", ".", ".."):
        parsed = parse_session_date(parent)
        if parsed is not None:
            return parsed
    stem = os.path.splitext(os.path.basename(song_path))[0]
    return parse_session_date(stem)


def _file_calendar_date(song_path: str) -> datetime:
    st = os.stat(song_path)
    birth = getattr(st, "st_birthtime", None)
    ts = birth if birth not in (None, 0) else st.st_mtime
    return datetime.fromtimestamp(ts)


def format_song_date(song_path: str | None = None, override: str | None = None) -> str:
    """Date drawn under the song title on Style A/B/C chrome.

    Priority: explicit override, parent folder name, audio filename,
    then file birthtime/mtime. ``datetime.now()`` is used only when no
    file exists and nothing else yielded a date.
    """
    if override and override.strip():
        parsed = parse_session_date(override)
        if parsed is not None:
            return format_chrome_date(parsed)
        return override.strip()

    if song_path:
        parsed = _date_from_audio_path(song_path)
        if parsed is not None:
            return format_chrome_date(parsed)
        if os.path.isfile(song_path):
            return format_chrome_date(_file_calendar_date(song_path))

    return format_chrome_date(datetime.now())
