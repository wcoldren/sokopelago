#!/usr/bin/env python3
"""Shared symmetry-aware canonicalization for Sokoban boards.

This is the one canonical-hash module the whole corpus toolchain reuses: the owned
generator (``generate_corpus``) for symmetry-aware dedup of constructed candidates, and
the ingest/annotate pipeline for deduping freely-licensed sets within and across corpora.

Two layers, deliberately separated:

* :func:`canonical` / :func:`canonical_hash` work on **raw glyph rows** — the
  lexicographically-smallest of a board's 8 dihedral forms (4 rotations x 2 reflections).
  Purely positional; no solver needed. This is the committed ``autoban`` dedup key and is
  test-pinned, so its behavior must never change. Extracted verbatim from
  ``generate_corpus`` (which now re-imports the three functions as ``_pad`` / ``_rotate90``
  / ``canonical`` aliases).

* :func:`canonical_player_normalized` is a **stronger** key that also collapses the
  player's position within its reachable region to a canonical cell (two boards identical
  but for where the player stands in the same region are the *same* puzzle). It needs the
  parsed ``Level`` + the solver's reachability, so it lives one layer up and is used only by
  ingest/dedup — never substituted for :func:`canonical`.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid importing the heavy solver/parser just to hash glyph rows
    from xsb_levels import Level

Rows = tuple[str, ...]


# --------------------------------------------------------------------------------------
# Glyph-level dihedral canonicalization (extracted verbatim from generate_corpus)
# --------------------------------------------------------------------------------------
def pad(rows: Rows) -> Rows:
    width = max(len(r) for r in rows)
    return tuple(r.ljust(width) for r in rows)


def rotate90(rows: Rows) -> Rows:
    """Rotate a rectangular glyph grid 90deg clockwise."""
    h = len(rows)
    return tuple("".join(rows[h - 1 - r][c] for r in range(h)) for c in range(len(rows[0])))


def canonical(rows: Rows) -> str:
    """A dedup key invariant under the 8 dihedral symmetries: the lexicographically
    smallest of the board's rotations/reflections. Equal canonical <=> same board up to
    rotation/mirror."""
    grid = pad(rows)
    forms: list[str] = []
    for _ in range(4):
        forms.append("\n".join(grid))
        forms.append("\n".join(tuple(r[::-1] for r in grid)))
        grid = rotate90(grid)
    return min(forms)


def canonical_hash(rows: Rows) -> str:
    """A short stable digest of :func:`canonical` (for stamping a level's identity in the
    manifest). Same board up to rotation/mirror <=> same hash."""
    return hashlib.sha1(canonical(rows).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------------------
# Reachability-aware canonicalization (player normalized within its region)
# --------------------------------------------------------------------------------------
# In Sokoban only the player's *region* matters, not the exact cell it stands on: two boards
# identical but for where the player sits in the same reachable component are the same puzzle.
# Folding that in correctly has to compose with the dihedral fold — normalizing the player to
# one cell *before* rotating fails, because "the canonical cell" is orientation-dependent. So
# the canonical form is the orbit-minimum over BOTH the 8 transforms AND every legal player
# placement within its reachable region. Pure glyph work — no solver needed (the region is
# just a flood fill over non-wall, non-box cells).
_BLOCKED = frozenset("#$*")  # wall or box — impassable to the player


def _player_cell(grid: list[list[str]]) -> tuple[int, int]:
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in "@+":
                return x, y
    raise ValueError("board has no player glyph")


def _reachable_region(grid: list[list[str]], start: tuple[int, int]) -> list[tuple[int, int]]:
    """4-connected component of player-passable cells (floor/goal) reachable from ``start``
    without crossing a wall or box — the same component the solver normalizes over."""
    h, w = len(grid), len(grid[0])
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and grid[ny][nx] not in _BLOCKED:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return sorted(seen)


def _region_canonical_rendering(rows: Rows) -> str:
    """Lexicographically smallest rendering of ``rows`` over every legal placement of the
    player within its reachable region (boxes/walls/goals fixed). The player cell is erased to
    its underlying floor/goal first, then each region cell is tried."""
    grid = [list(r) for r in pad(rows)]
    px, py = _player_cell(grid)
    region = _reachable_region(grid, (px, py))
    grid[py][px] = "." if grid[py][px] == "+" else " "  # erase player to underlying tile
    best: str | None = None
    for x, y in region:
        under = grid[y][x]
        grid[y][x] = "+" if under == "." else "@"
        rendering = "\n".join("".join(r) for r in grid)
        grid[y][x] = under
        if best is None or rendering < best:
            best = rendering
    assert best is not None  # region always contains the player's own cell
    return best


def canonical_player_normalized(level: Level) -> str:
    """Dihedral-invariant **and** player-region-invariant canonical key for dedup: the
    orbit-minimum over the 8 transforms, each rendered with the player at the region-canonical
    cell for that orientation."""
    grid = pad(level.rows)
    forms: list[str] = []
    for _ in range(4):
        forms.append(_region_canonical_rendering(grid))
        forms.append(_region_canonical_rendering(tuple(r[::-1] for r in grid)))
        grid = rotate90(grid)
    return min(forms)


def canonical_player_normalized_hash(level: Level) -> str:
    """Short stable digest of :func:`canonical_player_normalized` — the stamped dedup identity."""
    return hashlib.sha1(canonical_player_normalized(level).encode("utf-8")).hexdigest()[:16]
