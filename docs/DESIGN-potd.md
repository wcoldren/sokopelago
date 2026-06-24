# Design: Puzzle of the Day — corpus overlap (repeated puzzles)

Status: **known limitation — accepted for now.** Revisit when the corpus grows further or a
reserved/owned POTD pool exists.

## The pool (since 0.8.0)

POTD draws its daily level from the **curated** cross-corpus pool (`data/curated.json`), restricted
to push-solvable puzzles: the build drops the generated `autoban` set and the whole `pullban` set
(its pull-gated levels need a Pull control the POTD page lacks), plus any explicitly pull-required
level — see `buildDailyPool` in `client/src/potd/pool.ts`. That leaves **470** fully-solved puzzles
spanning Microban I–III, Sasquatch I–IX, and XSokoban. Each entry keeps a `source` tag
(`"sasquatch7:33"`), so the day is labeled by its origin set (e.g. "Sasquatch VII #33") and the
rating event records the source corpus + number rather than the pool index.

## The issue

POTD draws its daily level from a shared pool, so a player can be served a puzzle they've already
played. Two facets:

- **Cross-mode repeat:** the level was seen elsewhere before POTD served it (solo/demo, a prior
  AP run, or an earlier POTD day).
- **POTD cycling:** a fixed pool served one-per-day eventually exhausts and repeats. As of 0.8.1
  selection walks a fixed permutation of the pool (see the *Non-repeating date schedule* mitigation
  below), so there is **no repeat until the whole pool is exhausted** — the 470-entry curated pool ≈
  15 months before any repeat (vs the old microban-only ~5 months).

## Root tension

POTD is intentionally the **same** puzzle for everyone, so ratings are comparable. That conflicts
with per-player novelty, and it **can't be solved per-player** without breaking the shared-puzzle
property. The mitigations are therefore all pool-level, not per-player.

## Pool-level mitigations (when revisited)

- **Grow the corpus** (curation / generation) → longer cycle before any repeat.
- **Reserve a POTD-only pool** (held-out, or owned-generated, never used in solo) → kills
  cross-mode repeats cleanly. Ties to the owned-generation path.
- **Non-repeating date schedule** — *implemented in 0.8.1.* Selection walks a fixed deterministic
  permutation of the pool indexed by day number (`client/src/potd/select.ts`), so any window of
  `poolSize` consecutive days shows each puzzle exactly once — no repeat until the pool is exhausted
  (then the same order repeats). Earlier builds hashed the date string, which allowed repeats before
  exhaustion.
- **Acknowledge, don't avoid** — a gentle "you've played this before" badge derived from the
  existing per-level stats (`client/src/engine/stats.ts`), without changing the shared puzzle.

Revisit when the corpus grows or a reserved/owned POTD pool exists.
