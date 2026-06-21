# Design: augment the pullban corpus (Pull-tier robustness)

Status: **DONE (2026-06-21).** pullban expanded **10 → 30 levels** (pull-gated **60% → 30%**), all
solver-verified, and the speculative Pull-item late-placement gate was **removed** (it caused
6–42% fill failures once a bigger corpus made it engage). Net result: pull seeds now fill **0/150
across `levels_per_region` 5/3/2** (was 5–100%). PATCH-class (changes generated output but breaks no
contract — no new datapackage IDs, no `slot_data`/option change); lands on `dev`, version decided at
release (fold into untagged 0.7.0 or tag 0.7.1).

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
- **The 0.7 Pull-item late-placement floor can't engage.** With so few worlds the count-floor
  chain stays at 0, and the deep worlds tend to hold pull-gated levels, so there is no eligible
  late host → the floor stays in its safe **fallback (disabled)**. The feature is implemented,
  correct, and never makes a fill worse — but **dormant with the shipped corpus.** See
  `_effective_floors` / `_pull_item_host_eligible` / `_has_pull_item_host` and
  `TestPullItemFloorLogic` in `apworld/sokopelago/test/test_chaining.py`.

## The fix: a larger, lower-pull-ratio pull corpus

Author/source more **push-solvable (non-pull) Sokoban levels** for the pull corpus and raise the
total count, so the pull-gated *fraction* drops well below 50%. Concretely, aim for something
like **~30–40 levels with ≤ ~1/3 pull-gated**. That:

1. Gives the Pull item and the early keys many reachable non-pull homes + real filler budget →
   robust pull fills at any `levels_per_region` (including the zero-slack `=1` case, because the
   non-pull hosts now dominate);
2. Produces enough worlds for the count-floor chain to rise, so the **Pull-item late-placement
   floor actually activates** — Pull lands in a genuinely late sphere, delivering the intended
   "don't trivialise early push puzzles by getting Pull first" behaviour;
3. Makes the expert tier feel like a progression rather than 10 puzzles.

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

It **changes generated output** for pullban seeds, but under the (contract-based) `VERSIONING.md`
that is a **PATCH**, not a minor: it breaks no contract — no new location/item IDs, no `slot_data`
schema change, no option change. So this ships as **`0.7.1`**.

## Scope / sequencing

- **0.7.0 (this release):** boss gate + count-floor chaining + the Pull-item floor *logic*
  (dormant, safe fallback). pullban untouched.
- **0.7.1 (this follow-up):** the augmented pullban corpus, which *activates* the Pull-item floor
  and makes pull seeds robustly fillable at all region sizes. Pairs with the roadmap's deferred
  "larger pull corpus" item. (A patch — corpus content, no contract change.)

## Tests to add with the corpus change

- Pull seeds fill reliably across `levels_per_region` (including `= 1`) on the new corpus — the
  WorldTestBase fill battery over several configs.
- The Pull-item floor is now **active** on a representative config, and the Pull item is never
  placed before its floor sphere (promote the dormant-path assertions in `TestPullItemFloorLogic`
  to a live fill assertion once a host reliably exists).
- The pull-gated fraction invariant (e.g. assert `< 0.5` of the corpus is `requires_pull`).
