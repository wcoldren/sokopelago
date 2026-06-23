# Known issues

Current rough edges, especially around the **experimental expanded corpus pool** (`curated` + the
newly-ingested Microban II/III, Sasquatch I–IX, XSokoban 90). The original `microban`/`pullban`/
`autoban` corpora are unaffected.

## The expanded pool is unbalanced / contains very hard puzzles

The `curated` pool and the new sets are **experimental**. They mix easy→brutal: 26 levels were solved
only by an external solver, 85 by a non-optimal greedy search, and the source sets (Sasquatch,
XSokoban) contain huge puzzles (up to hundreds of boxes — those are excluded from `curated` as
unsolved, but the sets are browsable in solo). The per-level **difficulty and "fun" ratings are a weak
prior** (lightly Chu-calibrated, see `tools/calibrate_scoring.py`) and overall **balance is untuned**.
Expect rough difficulty and treat ratings as approximate.

## `level_count` silently clamps to the eligible pool

Option interactions aren't pre-validated by Archipelago (option ranges are static and independent), so
some combos quietly produce fewer levels/worlds than requested:

- `max_difficulty` caps the candidate pool *before* selection; then
  `level_count = min(level_count, eligible)` and worlds = `level_count / levels_per_region`.

So e.g. `max_difficulty: easy` + `level_count: 100` + `levels_per_region: 10` does **not** give a
10×10: `curated` has ~90 easy levels → ~9 worlds (last short); `microban` has ~41 easy → ~5 worlds.
A generation **warning** is logged when this clamp happens (see it in the Generate.py output), but the
seed still generates with the smaller count. For a true 10×10, use `max_difficulty: any` (or a pool
with ≥ `level_count` levels at the chosen cap).
