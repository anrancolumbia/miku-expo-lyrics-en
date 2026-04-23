#!/usr/bin/env python3
"""Parse a JA / romaji / ZH triplet text file (stanzas separated by blank lines) into manual-mode JSON."""

import json
import re
import sys
from pathlib import Path


def classify(line: str) -> str:
    s = line.strip()
    if not s:
        return "blank"
    has_kana = bool(re.search(r"[\u3040-\u30ff]", s))
    has_han = bool(re.search(r"[\u4e00-\u9fff]", s))
    has_latin = bool(re.search(r"[a-zA-Z]", s))
    if has_latin and not has_kana and not has_han:
        return "romaji"
    if has_kana:
        return "ja"
    if has_han:
        return "zh"
    return "other"


def main():
    txt_path = Path(sys.argv[1])
    slug, title, artist = sys.argv[2], sys.argv[3], sys.argv[4]
    text = txt_path.read_text(encoding="utf-8")
    # Process stanzas
    stanzas = re.split(r"\n\s*\n", text.strip())
    pairs = []
    for stanza in stanzas:
        lines = [l.strip() for l in stanza.splitlines() if l.strip()]
        # Group JA lines and ZH lines; discard romaji
        ja_lines = [l for l in lines if classify(l) == "ja"]
        zh_lines = [l for l in lines if classify(l) == "zh"]
        # Strip ruby annotations (kanji(kana)) → keep kanji only
        ja_lines = [re.sub(r"[(（][\u3040-\u309f]+[)）]", "", l) for l in ja_lines]
        # Pair by index
        for i in range(max(len(ja_lines), len(zh_lines))):
            ja = ja_lines[i] if i < len(ja_lines) else ""
            zh = zh_lines[i] if i < len(zh_lines) else ""
            if ja or zh:
                pairs.append({"ja": ja, "zh": zh})
    out = {
        "id": slug,
        "title": title,
        "artist": artist,
        "mode": "manual",
        "lines": pairs,
    }
    outpath = Path(__file__).resolve().parent.parent / "data" / "songs" / f"{slug}.json"
    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outpath}: {len(pairs)} lines")


if __name__ == "__main__":
    main()
