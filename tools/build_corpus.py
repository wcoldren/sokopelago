#!/usr/bin/env python3
"""Offline data-prep: build the bundled level manifest the apworld consumes.

Parses the canonical corpus ``levels/microban.xsb`` and writes
``apworld/sokopelago/data/microban.json`` — a list of ``{"n", "name"}`` entries,
one per level. This is the static data table the ROADMAP calls for: the apworld
reads it at import to know how many levels exist and their display names. It NEVER
solves Sokoban; it only splits levels and reads titles.

The level/title handling mirrors the TypeScript parser in ``client/src/xsb.ts``:
a ``; N`` line is a level title, a ``'name'`` line is an optional subtitle, blank
lines separate levels, and a board row is a line of only board glyphs containing at
least one non-space glyph.

Run:  python tools/build_corpus.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "levels" / "microban.xsb"
OUT = REPO_ROOT / "apworld" / "sokopelago" / "data" / "microban.json"

BOARD_CHARS = re.compile(r"^[#@+$*. ]+$")
NON_SPACE_GLYPH = re.compile(r"[#@+$*.]")
TITLE_LINE = re.compile(r"^;\s*(\d+)\s*$")
SUBTITLE_LINE = re.compile(r"^'(.*)'$")


def is_board_row(line: str) -> bool:
    return bool(line) and bool(BOARD_CHARS.match(line)) and bool(NON_SPACE_GLYPH.search(line))


def parse_levels(text: str) -> list[dict[str, object]]:
    """Return [{"n": int, "name": str}, ...] in corpus order."""
    levels: list[dict[str, object]] = []
    block_has_rows = False
    pending_num: int | None = None
    pending_sub: str | None = None

    def flush() -> None:
        nonlocal block_has_rows, pending_num, pending_sub
        if not block_has_rows:
            return
        num = pending_num if pending_num is not None else len(levels) + 1
        name = f"{num} — {pending_sub}" if pending_sub else str(num)
        levels.append({"n": num, "name": name})
        block_has_rows = False
        pending_num = None
        pending_sub = None

    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if is_board_row(line):
            block_has_rows = True
            continue
        flush()
        trimmed = line.strip()
        m_num = TITLE_LINE.match(trimmed)
        if m_num:
            pending_num = int(m_num.group(1))
            continue
        m_sub = SUBTITLE_LINE.match(trimmed)
        if m_sub:
            pending_sub = m_sub.group(1)
    flush()
    return levels


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(f"corpus not found: {CORPUS}")
    levels = parse_levels(CORPUS.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(levels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(levels)} levels -> {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
