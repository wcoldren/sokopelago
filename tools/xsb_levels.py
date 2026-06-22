#!/usr/bin/env python3
"""Shared XSB corpus parser for the offline data-prep tools.

Both ``build_corpus.py`` (names-only manifest) and ``solve_corpus.py`` (enriched
manifest with solutions/par/difficulty) parse the canonical ``levels/microban.xsb``
through this module, so the level splitting, numbering, and board geometry stay
identical to the TypeScript client parser (``client/src/xsb.ts``).

Level/title handling mirrors that parser exactly:
  - a ``; N`` line is a level title,
  - a ``'name'`` line is an optional subtitle,
  - blank/other lines separate levels,
  - a board row is a line of only board glyphs containing at least one non-space
    glyph.

Board glyphs:  ``#`` wall · (space) floor/outside · ``@`` player · ``+`` player on
goal · ``$`` box · ``*`` box on goal · ``.`` goal.

This module never solves Sokoban — it only splits levels and reads geometry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Known corpora: name -> canonical XSB source. ``microban`` is the v1 corpus; ``pullban``
# is the Phase 5 expert corpus of original pull-required levels; ``autoban`` is the
# in-house generated corpus (see ``tools/generate_corpus.py``), original by construction.
CORPORA: dict[str, Path] = {
    "microban": REPO_ROOT / "levels" / "microban.xsb",
    "pullban": REPO_ROOT / "levels" / "pullban.xsb",
    "autoban": REPO_ROOT / "levels" / "autoban.xsb",
}
CORPUS = CORPORA["microban"]  # default (backwards-compatible)


def corpus_xsb(name: str) -> Path:
    """Canonical XSB source path for a corpus name."""
    return CORPORA[name]


def manifest_json(name: str) -> Path:
    """Bundled manifest path the apworld/client consume for a corpus name."""
    return REPO_ROOT / "apworld" / "sokopelago" / "data" / f"{name}.json"


BOARD_CHARS = re.compile(r"^[#@+$*. ]+$")
NON_SPACE_GLYPH = re.compile(r"[#@+$*.]")
TITLE_LINE = re.compile(r"^;\s*(\d+)\s*$")
SUBTITLE_LINE = re.compile(r"^'(.*)'$")

Cell = tuple[int, int]  # (x, y); origin top-left, +x right, +y down


@dataclass(frozen=True)
class Level:
    """A parsed level: static geometry plus dynamic start positions.

    ``walkable`` is every Floor or Goal cell (where the player or a box may stand);
    everything else (wall / ragged outside padding) is impassable, matching the
    client's ``Tile.Floor``/``Tile.Goal`` walkability check.
    """

    n: int
    name: str
    width: int
    height: int
    walkable: frozenset[Cell]
    goals: frozenset[Cell]
    player: Cell
    boxes: frozenset[Cell]
    #: The raw XSB board rows, verbatim. Carried so the built manifest can bundle the
    #: board (the client renders from the manifest; ``levels/microban.xsb`` stays the
    #: canonical authoring source).
    rows: tuple[str, ...]


def is_board_row(line: str) -> bool:
    return bool(line) and bool(BOARD_CHARS.match(line)) and bool(NON_SPACE_GLYPH.search(line))


def _build_level(rows: list[str], index: int, num: int | None, sub: str | None) -> Level:
    height = len(rows)
    width = max(len(r) for r in rows)

    walkable: set[Cell] = set()
    goals: set[Cell] = set()
    boxes: set[Cell] = set()
    player: Cell | None = None

    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            if ch == "#":
                continue  # wall — not walkable
            if ch == " ":
                walkable.add((x, y))
            elif ch == ".":
                walkable.add((x, y))
                goals.add((x, y))
            elif ch == "$":
                walkable.add((x, y))
                boxes.add((x, y))
            elif ch == "*":
                walkable.add((x, y))
                goals.add((x, y))
                boxes.add((x, y))
            elif ch == "@":
                walkable.add((x, y))
                player = (x, y)
            elif ch == "+":
                walkable.add((x, y))
                goals.add((x, y))
                player = (x, y)

    n = num if num is not None else index + 1
    if player is None:
        raise ValueError(f"Level {n} has no player start (@ or +).")

    label = str(num) if num is not None else str(index + 1)
    name = f"{label} — {sub}" if sub else label

    return Level(
        n=n,
        name=name,
        width=width,
        height=height,
        walkable=frozenset(walkable),
        goals=frozenset(goals),
        player=player,
        boxes=frozenset(boxes),
        rows=tuple(rows),
    )


def parse_levels(text: str) -> list[Level]:
    """Parse XSB collection text into an ordered list of levels."""
    levels: list[Level] = []
    block: list[str] = []
    pending_num: int | None = None
    pending_sub: str | None = None

    def flush() -> None:
        nonlocal block, pending_num, pending_sub
        if not block:
            return
        levels.append(_build_level(block, len(levels), pending_num, pending_sub))
        block = []
        pending_num = None
        pending_sub = None

    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if is_board_row(line):
            block.append(line)
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


def load_corpus(path: Path = CORPUS) -> list[Level]:
    """Parse the canonical corpus file (``levels/microban.xsb`` by default)."""
    if not path.exists():
        raise SystemExit(f"corpus not found: {path}")
    return parse_levels(path.read_text(encoding="utf-8"))
