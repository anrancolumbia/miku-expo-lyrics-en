#!/usr/bin/env python3
"""Parse a Bahamut lyrics page (format: JA line / romaji line / ZH line) into manual-mode JSON."""

import json
import re
import sys
import html
import urllib.request
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}

CJK_JA = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
HAN_ONLY = re.compile(r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef，。！？、～0-9\s0-9a-zA-Z\(\)（）\-—]+$")
ROMAJI = re.compile(r"^[a-zA-Z0-9\s'\"\-\(\)（）,.\!\?]+$")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")


def extract_body(raw: str) -> str:
    # Bahamut article body (main content block)
    m = re.search(r'<div[^>]*class="article-content main"[^>]*>(.*?)<div[^>]*class="article-content more-item"', raw, re.S)
    if not m:
        m = re.search(r'<div[^>]*class="[^"]*c-article__content[^"]*"[^>]*>(.*?)<footer', raw, re.S)
    if not m:
        m = re.search(r'<article[^>]*>(.*?)</article>', raw, re.S)
    if not m:
        return raw
    body = m.group(1)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"</(p|div|li|h\d)>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    return html.unescape(body)


def classify(line: str) -> str:
    s = line.strip()
    if not s:
        return "blank"
    # Skip metadata
    for prefix in ("作詞", "作曲", "編曲", "PV", "唄", "中文翻譯", "中文翻译", "歌：", "翻譯：", "翻译："):
        if s.startswith(prefix):
            return "meta"
    has_kana = bool(re.search(r"[\u3040-\u30ff]", s))
    has_han = bool(re.search(r"[\u4e00-\u9fff]", s))
    has_latin = bool(re.search(r"[a-zA-Z]", s))
    # Pure romaji (latin letters, no CJK)
    if has_latin and not has_kana and not has_han:
        return "romaji"
    # Has kana = Japanese
    if has_kana:
        return "ja"
    # Has han but no kana = Chinese
    if has_han:
        return "zh"
    return "other"


def parse(url: str, slug: str, title: str, artist: str) -> dict:
    raw = fetch(url)
    text = extract_body(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Classify
    classified = [(l, classify(l)) for l in lines]
    # Find the lyrics block: find first 'ja' line and start from there
    start = next((i for i, (_, c) in enumerate(classified) if c == "ja"), None)
    if start is None:
        return {"id": slug, "title": title, "artist": artist, "mode": "manual", "lines": []}
    # Walk: expect pattern ja, romaji(optional), zh, repeating
    pairs = []
    i = start
    while i < len(classified):
        line, cls = classified[i]
        if cls != "ja":
            i += 1
            continue
        ja = line
        zh = ""
        # Look ahead for matching zh (skip romaji/meta/blank)
        j = i + 1
        while j < len(classified):
            l2, c2 = classified[j]
            if c2 in ("romaji", "meta", "blank", "other"):
                j += 1
                continue
            if c2 == "zh":
                zh = l2
                j += 1
                break
            if c2 == "ja":
                break
            j += 1
        pairs.append({"ja": ja, "zh": zh})
        i = j if zh else i + 1
    return {
        "id": slug,
        "title": title,
        "artist": artist,
        "mode": "manual",
        "source": url,
        "lines": pairs,
    }


if __name__ == "__main__":
    url, slug, title, artist = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    out = parse(url, slug, title, artist)
    outpath = Path(__file__).resolve().parent.parent / "data" / "songs" / f"{slug}.json"
    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outpath}: {len(out['lines'])} lines")
