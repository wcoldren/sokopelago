# Design — Owned puzzle generator (`autoban`)

**Goal.** Produce an **original, owned** Sokoban corpus (`autoban`) with a target
difficulty spread, scored by the *existing* solver and emitted in the exact manifest schema
the apworld/client already consume. Generated levels are original by construction, so no
third-party attribution is needed. Tool: `tools/generate_corpus.py` (v1).

## Why this shape
Throughput is dominated by *solving*, which is steeply tiered (a trivial level solves in
~1 ms; a hard one runs for seconds). So the pipeline avoids ever solving junk and bounds
the hard tail:

```
reverse-construct (solvable by construction)
  -> cheap pre-filter (no solve)
  -> capped, parallel scoring solve (discard over-budget)
  -> calibrate difficulty -> tier -> keep-to-quota
```

with symmetry-aware dedup throughout and a fixed RNG seed.

## Key decisions

1. **Reverse-construction → solvable by construction.** Carve a room, place every box on a
   goal (a trivially-solved state), then scatter the boxes with legal *pulls*. The exact
   inverse of each construction pull is a forward *push* (the pull legality in
   `solve_corpus._search_pull`), so the scattered start state is guaranteed push-solvable —
   no solvability solves are wasted, and no Pull ability is needed (push-only, v1 scope).
   Pulls are biased to move a box *away* from its nearest goal (lone-box push distance);
   purely random pulls cancel out and leave a short optimum that scores easy.

2. **Capped scoring reuses `solve()` verbatim, with a deterministic gate.** Scoring runs a
   single optimal-A* phase under a **node-budget** cap (the primary keep/discard signal)
   with the per-phase wall-clock deadline disabled, so the *node budget* — not machine
   speed — decides every outcome. A wall-clock kill is only a safety backstop. One phase
   keeps a discard cheap (1× the budget, not 7× across the full coverage ladder) and makes
   every kept level push-optimal. Parallelized across cores (the bottleneck is embarrassingly
   parallel).

3. **Microban-calibrated difficulty.** `_attach_difficulty(entries, ref_bounds=…)` normalizes
   each signal against a *fixed reference* (Microban's natively-solved bounds, registered as
   `CALIBRATION_REF = {"autoban": "microban"}`) and clamps to [0, 1], so `autoban`'s
   easy/medium/hard tiers mean what Microban's do — not merely "hardest in this pack". The
   external-solver outlier (Microban 153) is excluded from the reference so the absolute
   scale stays reachable. Calibrated scores are independent of pool-mates, so per-tier quota
   targeting is exact.

4. **Symmetry-aware dedup.** A level's key is the lexicographically smallest of its 8
   dihedral transforms. Candidates are deduped within the run and against every existing
   corpus.

5. **Determinism.** Same seed + params → identical pack. Generation is serial in the main
   process; scoring is pure per candidate and node-gated (no time dependence). The round
   (batch) size is fixed, *not* derived from `--workers`, so the pack is worker-count
   independent (batch granularity decides when per-tier quotas update, which steers which
   tier each construction targets).

6. **`score_quality(features)` seam.** A 0..1 quality/"fun" hook used only to rank
   within-tier when over-quota. v1 is a light placeholder; the POTD-trained fun-scorer drops
   in behind the same signature later.

## Output
- `levels/autoban.xsb` — canonical authoring source (provenance header comment).
- `apworld/sokopelago/data/autoban.json` — committed manifest, microban.json schema,
  produced by the canonical pipeline (`build_corpus_manifest` + `merge_boards`).
- `levels/autoban.meta.json` — generator version, seed, params, stats (provenance lives
  outside the consumed JSON, whose schema is fixed).
- Registered as a selectable corpus (`corpus.CORPUS_NAMES`, `Options.Corpus`). No apworld
  logic / client / POTD / solo-demo changes.

The committed v1 pack: **55 levels, 20/25/10 easy/medium/hard, seed 0**
(`--node-budget 300000`), difficulty 0.06–0.73 on the Microban-calibrated scale.

## Known v1 characteristics / limitations
- **Hard tier skews fiddly, not long.** Under the node-budget cap, `autoban`'s hard levels
  earn their tier mostly through search-node difficulty (congested, branchy) at modest par
  (≤ ~40), rather than very long solutions. If a larger/longer hard set is wanted, raise
  `--node-budget` (slower, lower yield) and/or the hard `TierSpec` scatter.
- **Regenerate with `generate_corpus.py`, not a bare re-solve.** The committed manifest is
  built with the generator's deterministic single-phase, node-capped scoring. A standalone
  `solve_corpus.py --corpus autoban` uses the full uncapped coverage ladder with real
  per-phase time deadlines, which can differ for the few hardest levels on a slow machine
  (if their optimal solve exceeds the 15 s phase-1 deadline). The generator is the
  machine-independent, reproducible producer.
- **Pull-requiring generation is out of scope** (needs `solve_pull` verification — a later
  effort). v1 is push-only by construction.
