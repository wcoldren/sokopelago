# Design: augment the pullban corpus (Pull-tier robustness)

Status: **DONE (2026-06-21).** pullban expanded **10 → 30 levels** (pull-gated **60% → 30%**), all
solver-verified, and the speculative Pull-item late-placement gate was **removed** (it caused
6–42% fill failures once a bigger corpus made it engage). Net result: pull seeds now fill **0/150
across `levels_per_region` 5/3/2** (was 5–100%). PATCH-class (changes generated output but breaks no
contract — no new datapackage IDs, no `slot_data`/option change); **shipped in 0.7.0** alongside
the boss-zone/chaining work.

> **Regen order matters:** `solve_corpus.py --corpus pullban` (enriches: par/solution/requires_pull/
> difficulty) **then** `build_corpus.py --corpus pullban` (restores the `board` field, preserving
> solver fields). solve-only drops boards.

> **Late-Pull, revisited.** The "acquire Pull late" intent is deferred: every filler-based
> restriction on the Pull item (deep-sphere or even just excluding World 1) leaves a fill-failure
> tail (1–42%), so it was dropped in favour of robustness. Pull is again a normal shuffleable
> progression item (still required to win, still gates `requires_pull` levels). A future fill-safe
> mechanism (e.g. deterministic pre-placement, accepting local Pull) could bring back a real late
> guarantee. The original problem analysis below is kept for that follow-up.

## The problem

`pull_logic` (the expert tier) hard-gates the `requires_pull` levels behind the **Pull** item.
The only pull corpus, `data/pullban.json`, is **10 levels, 6 of them pull-gated (60%)**:

```
n:            1 2 3 4 5 6 7 8 9 10
requires_pull:        ✓ ✓ ✓ ✓ ✓ ✓   (6/10)
```

That 60% pull-gated ratio — not the small size per se — is what starves the fill:

- **Only 4 non-pull "host" locations** exist for the Pull item and the early keys to live in
  (a location gated behind Pull can't host the very item that unlocks it). With so few hosts,
  the solo `fill_restrictive` pass is fragile and, at `levels_per_region == 1`, impossible:
  - At `levels_per_region == 1` the item budget is `level_count − (region_count−1) − 1 = 0`, an
    all-progression zero-slack fill in which 60% of slots are Pull-gated → **100% fill failure.**
    This is **pre-existing 0.6 behavior** (the unmodified `solve_count` goal fails identically),
    not a 0.7 regression. 0.7's boss gate alone (no pull) fills these layouts at 0% failure.
- *(Historical: a "Pull-item late-placement floor" was prototyped to keep Pull out of early
  spheres. With the 10-level corpus it never had an eligible late host and stayed dormant; once the
  expanded corpus made it engage it degraded fills, so it was removed — see "As shipped" below.)*

## The fix: a larger, lower-pull-ratio pull corpus

Author/source more **push-solvable (non-pull) Sokoban levels** for the pull corpus and raise the
total count, so the pull-gated *fraction* drops well below 50%. Concretely, aim for something
like **~30–40 levels with ≤ ~1/3 pull-gated**. That:

1. Gives the Pull item and the early keys many reachable non-pull homes + real filler budget →
   robust pull fills at any `levels_per_region` (including the zero-slack `=1` case, because the
   non-pull hosts now dominate);
2. Makes the expert tier feel like a progression rather than 10 puzzles.

(The original plan also hoped a larger corpus would let a Pull-item placement floor enforce
"acquire Pull late"; in practice any such restriction degraded fills, so that idea was dropped —
see "As shipped".)

### Constraints / non-negotiables

- **Never solve at generation time.** New levels must be run through the **pull-aware
  `tools/solve_corpus.py --corpus pullban`** offline to regenerate `data/pullban.json` with
  `par` / `moves` / `difficulty` / `solution` / `requires_pull`. The generator only reads the
  manifest. (See `games/...` solver notes / [[sokopelago-solver]].)
- **Level provenance + licensing** must be tracked in `CREDITS.md` like the Microban set.
- **Each pull gate must be solver-proven**: a `requires_pull` level must be unsolvable push-only
  and solvable with Pull (the solver's pull-aware mode establishes this).

### Versioning

`LEVELS` (the datapackage location table) is built from the **microban** manifest, registering
`Solve/par/eff Microban 1..155` and `World 2..155` keys. pullban reuses those IDs (its levels are
`n = 1..10 ≤ 155`). So **as long as the augmented pullban stays within `n ≤ 155`, it adds no new
location/item IDs** and the name→id map is unchanged.

It **changes generated output** for pullban seeds but breaks no contract (no new location/item
IDs, no `slot_data` schema change, no option change), so under the contract-based `VERSIONING.md`
it's PATCH-class — and it **shipped in `0.7.0`** alongside the boss-zone/chaining work rather than
as a separate tag.

## As shipped (0.7.0)

- pullban grew **10 → 30 levels**, pull-gated **60% → 30%** (21 host levels, 9 pull-required), every
  board solver-verified.
- The Pull-item late-placement floor was **tried and removed**: once the bigger corpus made it
  engage, the placement restriction caused 6–42% generation failures (even the gentlest "exclude
  World 1" variant was 1–2%). The corpus expansion alone is the fix — pull seeds now fill **~0%
  failure** at `levels_per_region` 5/3/2. Pull is a normal shuffleable progression item again.
- "Acquire Pull late" is **deferred** to a future fill-safe mechanism (e.g. deterministic
  pre-placement, accepting a local Pull) — the analysis above is kept for that follow-up.

## Tests (in place)

- `tests/test_corpus_and_layout.py::TestPullbanManifest`: all solved, both host + pull levels,
  solutions replay, gated levels push-unsolvable, and the **count ≥ 24 / pull-gated fraction < 0.5**
  invariant.
- Fill robustness was confirmed by a stress sweep over pullban `pull_logic` seeds (~0 failures at
  lpr 5/3/2).
