#!/usr/bin/env python3
"""Migrate song JSONs from {t, ja, zh} to {t, ja, en} with empty EN (to be filled)."""

import json
from pathlib import Path

SONGS_DIR = Path(__file__).resolve().parent.parent / "data" / "songs"

for path in sorted(SONGS_DIR.glob("*.json")):
    d = json.loads(path.read_text())
    new_lines = []
    for ln in d.get("lines", []):
        new_lines.append({
            "t": ln.get("t"),
            "ja": ln.get("ja", ""),
            "en": "",
        })
    d["lines"] = new_lines
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  migrated {path.name}: {len(new_lines)} lines")
print("Done.")
