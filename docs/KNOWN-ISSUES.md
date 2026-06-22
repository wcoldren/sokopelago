# Known issues

Current rough edges, especially around the **experimental expanded corpus pool** (`curated` + the
newly-ingested Microban II/III, Sasquatch I–IX, XSokoban 90). The original `microban`/`pullban`/
`autoban` corpora are unaffected.

## Pull is always available for non-Microban corpora (intentional for now)

**What you see:** in both solo and multiworld, the **Pull** ability/button is usable on any corpus
other than `microban`, even when the seed didn't grant a Pull item.

**Why:** `Session.canPull` is `!pull_logic || pullReceived` (`client/src/ap/session.ts`), and the Pull
button shows whenever `loadedCorpus !== "microban"` or `pull_logic` is on (`client/src/main.ts`,
`updateValveButtons`). The `curated` pool leaves `pull_logic` off, so pull is freely available.

**Why we're leaving it on:** it's currently **load-bearing**. The `curated` pool includes **6
`requires_pull` levels** (from `pullban`) — with `pull_logic` off the apworld neither gates them nor
adds a Pull item, so Archipelago's fill assumes they're push-solvable when they aren't. The free
client-side pull is the only thing keeping such a seed winnable. It also gives an escape on the
genuinely brutal levels (26 external-solved + 85 greedy/non-optimal in `curated`). Players who want a
pure push experience can simply not use it.

**Proper fix (coupled — don't just disable the client pull):** pick one, *then* gate the client pull
behind `pull_logic`:
- (a) filter `requires_pull` levels out of `curated` (`tools/build_pool.py`), or
- (b) set `pull_logic` on for `curated` and gate those levels behind the Pull item, or
- (c) make free-pull an explicit opt-in setting.

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
10×10: `curated` has ~93 easy levels → ~10 worlds (last short); `microban` has ~41 easy → ~5 worlds.
A generation **warning** is logged when this clamp happens (see it in the Generate.py output), but the
seed still generates with the smaller count. For a true 10×10, use `max_difficulty: any` (or a pool
with ≥ `level_count` levels at the chosen cap).
