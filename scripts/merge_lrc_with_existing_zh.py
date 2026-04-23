#!/usr/bin/env python3
"""Merge a Japanese LRC with an existing song JSON that already has JA+ZH pairs.

Use case: we had a manual-mode song parsed from a bilingual source (JA+ZH, no timestamps),
and later got an LRC with precise Japanese timestamps. This script keeps the LRC as the
source of truth for lines + timing, and pulls the matching ZH from the old file when the
normalized JA matches.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    # Strip all whitespace and punctuation
    s = re.sub(r"[\s\u3000『』「」【】\(\)（）\[\]〈〉《》、。，．!！?？:：;；ー～〜'\"]", "", s)
    return s.lower()


def parse_lrc(text: str) -> list[dict]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        m = LRC_RE.match(line)
        if not m:
            continue
        txt = m.group(3).strip()
        if not txt:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2))
        out.append({"t": round(t, 2), "ja": txt, "zh": ""})
    out.sort(key=lambda d: d["t"])
    return out


def main():
    lrc_path = Path(sys.argv[1])
    slug = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else None
    artist = sys.argv[4] if len(sys.argv) > 4 else None

    ROOT = Path(__file__).resolve().parent.parent
    old_path = ROOT / "data" / "songs" / f"{slug}.json"
    old = json.loads(old_path.read_text()) if old_path.exists() else {"lines": []}
    zh_lookup = {}
    for ln in old.get("lines", []):
        key = normalize(ln.get("ja", ""))
        if key and ln.get("zh"):
            zh_lookup[key] = ln["zh"]

    lrc_lines = parse_lrc(lrc_path.read_text(encoding="utf-8"))
    hits = 0
    for ln in lrc_lines:
        key = normalize(ln["ja"])
        if key in zh_lookup:
            ln["zh"] = zh_lookup[key]
            hits += 1
            continue
        # Fallback: try partial match — the longest old line that is a substring of this one, or vice versa
        best = ""
        best_len = 0
        for k, v in zh_lookup.items():
            if not k: continue
            if k in key or key in k:
                overlap = min(len(k), len(key))
                if overlap > best_len:
                    best_len = overlap
                    best = v
        if best and best_len >= 3:
            ln["zh"] = best
            hits += 1

    merged = {
        "id": slug,
        "title": title or old.get("title", slug),
        "artist": artist or old.get("artist", ""),
        "mode": "timed",
        "source": "lrc-merged",
        "lines": lrc_lines,
    }
    old_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {old_path}: {len(lrc_lines)} LRC lines, {hits} with zh from old file")


if __name__ == "__main__":
    main()
