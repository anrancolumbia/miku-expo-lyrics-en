#!/usr/bin/env python3
"""Batch fetch bilingual (JA+ZH) timed lyrics from NetEase for the Miku Expo setlist."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETLIST_FILE = ROOT / "data" / "setlist.json"
SONGS_DIR = ROOT / "data" / "songs"
OVERRIDES_FILE = ROOT / "scripts" / "overrides.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Referer": "https://music.163.com/",
}

SETLIST = [
    ("01-teo", "テオ", "Omoi"),
    ("02-kimagure-mercy", "気まぐれメルシィ", "shizuko"),
    ("03-culture", "カルチャ", "TSUMIKI"),
    ("04-2d-dream-fever", "2次元ドリームフィーバー", "PolyphonicBranch"),
    ("05-darling-dance", "ダーリンダンス", "Kairiki bear"),
    ("06-raspberry-monster", "Raspberry*Monster", "HoneyWorks"),
    ("07-solar-system-disco", "Solar System Disco", "NayutalieN"),
    ("08-play-with-fire", "Play with Fire", "Camellia"),
    ("09-worlds-end-dancehall", "ワールズエンド・ダンスホール", "wowaka"),
    ("10-tyqoon", "TYQOON", "Sohbana"),
    ("11-rettou-joutou", "劣等上等", "Giga"),
    ("12-8hit", "8 1 6", "PinocchioP"),
    ("13-roki", "ロキ", "みきとP"),
    ("14-super-cat", "結局リンちゃんはスーパーキャットになれなかったよ", "鏡音リン"),
    ("15-sweet-magic", "スイートマジック", "Junky"),
    ("16-amazing-dolce", "Amazing Dolce", "ひとしずくP"),
    ("17-caged-flower", "囚われのマリオネット", "KAITO"),
    ("18-godish", "神っぽいな", "ピノキオピー"),
    ("19-love-is-war", "恋は戦争", "supercell"),
    ("20-patchwork-staccato", "ツギハギスタッカート", "とあ"),
    ("21-room-for-fantasy", "Room for a Fantasy", "nostraightanswer"),
    ("22-somedays-coming", "Someday'z Coming", "Shoten Taro"),
    ("23-never-die", "Never Die", "Yuyoyuppe"),
    ("24-wanderlast", "THE WANDERLAST", "sasakure.UK"),
    ("25-drop-pop-candy", "ドロップポップキャンディ", "Giga"),
    ("26-ohedo-julianight", "お江戸ジュリアナイト", "みきとP"),
    ("27-magical-cure", "Magical Cure! Love Shot!", "Mitchie M"),
    ("28-catch-the-wave", "Catch the Wave", "kz"),
    ("29-shake-it", "shake it!", "emon"),
    ("30-39", "39", "sasakure.UK DECO*27"),
    ("31-connect-commune", "CONNECT:COMMUNE", "FLAVOR FOLEY"),
    ("32-artifact", "Artifact", "buzzG"),
    ("33-decorator", "DECORATOR", "livetune"),
    ("34-odds-and-ends", "ODDS&ENDS", "ryo"),
]


def search_song(title: str, artist: str) -> int | None:
    """Search NetEase, return best-match song id."""
    query = f"{title} {artist}"
    url = (
        "https://music.163.com/api/search/get?"
        + urllib.parse.urlencode({"s": query, "type": 1, "limit": 10})
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    songs = (data.get("result") or {}).get("songs") or []
    if not songs:
        return None
    # Prefer exact title match + artist hit; fall back to first result.
    t_norm = title.lower().replace(" ", "")
    for s in songs:
        if s["name"].lower().replace(" ", "") == t_norm:
            artists = " ".join(a["name"] for a in s["artists"]).lower()
            if any(tok.lower() in artists for tok in artist.split()):
                return s["id"]
    return songs[0]["id"]


def fetch_lyric(song_id: int) -> tuple[str, str]:
    """Return (japanese_lrc, chinese_lrc)."""
    url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    ja = (data.get("lrc") or {}).get("lyric") or ""
    zh = (data.get("tlyric") or {}).get("lyric") or ""
    return ja, zh


LRC_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def parse_lrc(text: str) -> list[tuple[float, str]]:
    """Parse LRC text into sorted (seconds, text) pairs. Drops metadata and empty lines."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LRC_RE.match(line)
        if not m:
            continue
        mm, ss, txt = m.group(1), m.group(2), m.group(3).strip()
        # Skip metadata (composer/title/etc. — usually first seconds of the track)
        if not txt or txt.startswith("作词") or txt.startswith("作曲") or txt.startswith("编曲"):
            continue
        t = int(mm) * 60 + float(ss)
        out.append((t, txt))
    out.sort(key=lambda x: x[0])
    return out


def merge(ja_lines: list[tuple[float, str]], zh_lines: list[tuple[float, str]]) -> list[dict]:
    zh_map = {round(t, 2): text for t, text in zh_lines}
    merged = []
    for t, ja in ja_lines:
        zh = zh_map.get(round(t, 2), "")
        merged.append({"t": round(t, 2), "ja": ja, "zh": zh})
    return merged


def build_song(slug: str, title: str, artist: str) -> dict:
    song_id = search_song(title, artist)
    if song_id is None:
        print(f"  ✗ not found: {title} / {artist}")
        return {"id": slug, "title": title, "artist": artist, "mode": "manual", "lines": []}
    ja_raw, zh_raw = fetch_lyric(song_id)
    ja_lines = parse_lrc(ja_raw)
    zh_lines = parse_lrc(zh_raw)
    if not ja_lines:
        print(f"  ⚠ no JA lyrics for {title}; manual mode")
        return {"id": slug, "title": title, "artist": artist, "mode": "manual", "lines": [], "neteaseId": song_id}
    # Heuristic: if fewer than ~5 timestamps, probably not a timed LRC
    mode = "timed" if len(ja_lines) >= 5 else "manual"
    lines = merge(ja_lines, zh_lines)
    zh_hits = sum(1 for ln in lines if ln["zh"])
    print(f"  ✓ {title}: {len(lines)} lines, {zh_hits} w/ zh, mode={mode}, id={song_id}")
    return {
        "id": slug,
        "title": title,
        "artist": artist,
        "mode": mode,
        "neteaseId": song_id,
        "lines": lines,
    }


def main():
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    overrides = {}
    if OVERRIDES_FILE.exists():
        overrides = json.loads(OVERRIDES_FILE.read_text())

    setlist_meta = []
    for slug, title, artist in SETLIST:
        print(f"[{slug}] {title} / {artist}")
        if slug in overrides:
            ov = overrides[slug]
            title = ov.get("title", title)
            artist = ov.get("artist", artist)
            if "neteaseId" in ov:
                print(f"  → override neteaseId={ov['neteaseId']}")
                ja_raw, zh_raw = fetch_lyric(ov["neteaseId"])
                ja_lines = parse_lrc(ja_raw)
                zh_lines = parse_lrc(zh_raw)
                mode = "timed" if len(ja_lines) >= 5 else "manual"
                lines = merge(ja_lines, zh_lines)
                zh_hits = sum(1 for ln in lines if ln["zh"])
                print(f"  ✓ {title}: {len(lines)} lines, {zh_hits} w/ zh, mode={mode}")
                song = {"id": slug, "title": title, "artist": artist, "mode": mode,
                        "neteaseId": ov["neteaseId"], "lines": lines}
            else:
                song = build_song(slug, title, artist)
        else:
            try:
                song = build_song(slug, title, artist)
            except Exception as e:
                print(f"  ✗ error: {e}")
                song = {"id": slug, "title": title, "artist": artist, "mode": "manual", "lines": []}
        (SONGS_DIR / f"{slug}.json").write_text(
            json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        setlist_meta.append({
            "id": slug,
            "title": song["title"],
            "artist": song["artist"],
            "mode": song["mode"],
        })
        time.sleep(0.3)  # be polite to NetEase

    SETLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETLIST_FILE.write_text(
        json.dumps({"concert": "Miku Expo 2026", "songs": setlist_meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manual_count = sum(1 for s in setlist_meta if s["mode"] == "manual")
    print(f"\nDone. {len(setlist_meta)} songs total, {manual_count} in manual mode.")


if __name__ == "__main__":
    main()
