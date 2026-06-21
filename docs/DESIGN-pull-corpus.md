# Design: augment the pullban corpus (Pull-tier robustness)

Status: **proposal / follow-up to 0.7.** Documents a fill-robustness problem in the expert Pull
tier and the corpus change that fixes it. No code logic change is required — this is offline
data work (level authoring + the pull-aware solver) plus a manifest regen. Recommended bump:
**MINOR (0.8.0)** — see [Versioning](#versioning) (it changes generation output even though it
adds no new datapackage IDs).

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

It still **changes generation output** for pullban seeds, though, which `VERSIONING.md` treats as
a world-affecting change (cf. the 0.6.0 difficulty rescore, which shipped as a MINOR). So the
honest bump is **MINOR → `0.8.0`**, not a patch. Shipping it as `0.7.1` would contradict the
project's own policy (a patch must not alter generation output); only do that if the policy is
deliberately relaxed for the pre-1.0 expert tier.

## Scope / sequencing

- **0.7.0 (this release):** boss gate + count-floor chaining + the Pull-item floor *logic*
  (dormant, safe fallback). pullban untouched.
- **0.8.0 (this follow-up):** the augmented pullban corpus, which *activates* the Pull-item floor
  and makes pull seeds robustly fillable at all region sizes. Pairs with the roadmap's deferred
  "larger pull corpus" item.

## Tests to add with the corpus change

- Pull seeds fill reliably across `levels_per_region` (including `= 1`) on the new corpus — the
  WorldTestBase fill battery over several configs.
- The Pull-item floor is now **active** on a representative config, and the Pull item is never
  placed before its floor sphere (promote the dormant-path assertions in `TestPullItemFloorLogic`
  to a live fill assertion once a host reliably exists).
- The pull-gated fraction invariant (e.g. assert `< 0.5` of the corpus is `requires_pull`).
