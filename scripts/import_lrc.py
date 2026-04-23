#!/usr/bin/env python3
"""Import a single LRC file as a timed song JSON. Put the LRC lines in `ja` (placeholder)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def parse(text: str) -> list[dict]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        m = LRC_RE.match(line)
        if not m:
            continue
        mm, ss, txt = m.group(1), m.group(2), m.group(3).strip()
        if not txt:
            continue
        t = int(mm) * 60 + float(ss)
        out.append({"t": round(t, 2), "ja": txt, "zh": ""})
    out.sort(key=lambda d: d["t"])
    return out


def main():
    lrc_path = Path(sys.argv[1])
    slug, title, artist = sys.argv[2], sys.argv[3], sys.argv[4]
    text = lrc_path.read_text(encoding="utf-8")
    lines = parse(text)
    song = {
        "id": slug,
        "title": title,
        "artist": artist,
        "mode": "timed",
        "source": "lrc-import",
        "lines": lines,
    }
    outpath = Path(__file__).resolve().parent.parent / "data" / "songs" / f"{slug}.json"
    outpath.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outpath}: {len(lines)} lines")


if __name__ == "__main__":
    main()
