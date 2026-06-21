# Design: Puzzle of the Day — corpus overlap (repeated puzzles)

Status: **known limitation — accepted for now, not blocking v0.7.1.** Revisit when the corpus
grows or a reserved/owned POTD pool exists.

## The issue

POTD draws its daily level from the shared corpus, so a player can be served a puzzle they've
already played. Two facets:

- **Cross-mode repeat:** the level was seen elsewhere before POTD served it (solo/demo, a prior
  AP run, or an earlier POTD day).
- **POTD cycling:** a fixed pool served one-per-day eventually exhausts and repeats (~155 Microban
  levels ≈ 5 months before a repeat is even *possible*).

## Root tension

POTD is intentionally the **same** puzzle for everyone, so ratings are comparable. That conflicts
with per-player novelty, and it **can't be solved per-player** without breaking the shared-puzzle
property. The mitigations are therefore all pool-level, not per-player.

## Pool-level mitigations (when revisited)

- **Grow the corpus** (curation / generation) → longer cycle before any repeat.
- **Reserve a POTD-only pool** (held-out, or owned-generated, never used in solo) → kills
  cross-mode repeats cleanly. Ties to the owned-generation path.
- **Non-repeating date schedule** — permute the whole pool so there's no repeat until the pool is
  exhausted. (The current selection hashes the date string, so a repeat is *possible* before
  exhaustion; a permutation removes that — see `client/src/potd/select.ts`.)
- **Acknowledge, don't avoid** — a gentle "you've played this before" badge derived from the
  existing per-level stats (`client/src/engine/stats.ts`), without changing the shared puzzle.

Revisit when the corpus grows or a reserved/owned POTD pool exists.
