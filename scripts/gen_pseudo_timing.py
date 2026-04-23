#!/usr/bin/env python3
"""Generate pseudo timestamps for manual-mode songs (evenly distributed)."""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONGS_DIR = ROOT / "data" / "songs"
SETLIST_FILE = ROOT / "data" / "setlist.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Fallback durations (seconds) when NetEase doesn't know or song has no id
DEFAULT_DURATION = 210  # 3:30

# Manual-set durations for songs without NetEase data
MANUAL_DURATIONS = {
    "08-play-with-fire": 202,   # ヒアソビ ~3:22
    "14-super-cat": 245,        # すーぱーぬこ ~4:05
    "27-magical-cure": 210,     # guess
    "28-catch-the-wave": 230,   # kz ~3:50
}

INTRO_SEC = 8    # skip first N seconds (typical intro)
OUTRO_SEC = 12   # leave last N seconds as outro


def fetch_duration(song_id: int) -> int | None:
    """Fetch song duration in seconds from NetEase detail API."""
    url = f"https://music.163.com/api/song/detail/?id={song_id}&ids=%5B{song_id}%5D"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        songs = data.get("songs") or []
        if songs:
            return int(songs[0].get("duration", 0) / 1000)
    except Exception as e:
        print(f"  duration fetch failed: {e}")
    return None


def main():
    setlist = json.loads(SETLIST_FILE.read_text())
    changed = []
    for meta in setlist["songs"]:
        sid = meta["id"]
        path = SONGS_DIR / f"{sid}.json"
        if not path.exists():
            continue
        song = json.loads(path.read_text())
        if song.get("mode") != "manual":
            continue
        lines = song.get("lines") or []
        if not lines:
            continue
        # Already has timestamps? skip
        if any(("t" in l) for l in lines):
            continue
        # Determine duration
        dur = MANUAL_DURATIONS.get(sid)
        if dur is None and song.get("neteaseId"):
            dur = fetch_duration(song["neteaseId"])
        if dur is None:
            dur = DEFAULT_DURATION

        n = len(lines)
        usable = max(dur - INTRO_SEC - OUTRO_SEC, n * 1.5)
        step = usable / max(n - 1, 1)
        for i, ln in enumerate(lines):
            ln["t"] = round(INTRO_SEC + i * step, 2)

        song["mode"] = "pseudo"  # pseudo-timed
        song["lines"] = lines
        song["duration"] = dur
        path.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")
        meta["mode"] = "pseudo"
        changed.append(sid)
        print(f"  + {sid}: {n} lines over {dur}s")

    SETLIST_FILE.write_text(json.dumps(setlist, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nUpdated {len(changed)} songs: {changed}")


if __name__ == "__main__":
    main()
