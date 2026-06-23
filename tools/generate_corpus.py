#!/usr/bin/env python3
"""Owned puzzle generator: build an original Sokoban corpus by reverse-construction.

This produces the in-house ``autoban`` corpus — levels that are *original by
construction* (no third-party puzzles, no attribution needed) with a target difficulty
spread, scored by the project's existing solver and emitted in the exact manifest schema
the apworld and client already consume.

The architecture follows the throughput reality: generation is cheap, *solving* is the
cost and it is steeply tiered (a trivial level solves in ~1 ms, a hard one can run for
seconds). So the loop is:

  reverse-construct (solvable by construction) -> cheap pre-filter -> capped, parallel
  scoring solve (discard over-budget) -> calibrate difficulty -> tier -> keep-to-quota,

with symmetry-aware dedup throughout and a fixed RNG seed for reproducibility.

* **Reverse-construction** (``construct_candidate``): carve a room, place every box on a
  goal (a trivially-solved state), then scatter the boxes with legal *pulls*. The exact
  inverse of each construction pull is a forward *push* (see ``solve_corpus._search_pull``
  lines 730-733), so the scattered start state is push-solvable by construction — no
  solvability solves are ever wasted on junk, and no Pull ability is required (v1 scope).
* **Scoring** reuses ``solve_corpus.solve`` verbatim under a deterministic node-budget gate
  (the primary keep/discard signal) plus a wall-clock kill (a safety backstop). The
  per-phase time deadlines inside the solver are disabled for scoring so the node budget —
  not machine speed — decides the outcome, keeping the pack reproducible.
* **Difficulty** is calibrated against Microban's native bounds (``solve_corpus`` registers
  ``autoban -> microban`` in ``CALIBRATION_REF``), so a tier here means what it means in
  Microban rather than merely "hardest in this pack". Calibrated scores are independent of
  pool-mates, so per-tier quota targeting is exact.

The committed manifest is written *directly* from the push-optimal scores computed during
selection (each via ``solve_corpus.solve`` + ``_attach_difficulty``), in the exact
microban.json schema — not re-solved through ``solve_corpus``'s full coverage ladder, whose
per-phase time deadlines would let the optimal phase time out on the hardest levels and
record a suboptimal greedy par. A ``levels/autoban.meta.json`` sidecar records the generator
version, seed, and parameters (the consumed JSON schema is fixed, so provenance lives
outside it); its presence also makes ``solve_corpus.build_corpus_manifest`` refuse a naive
re-solve.

Run:  python tools/generate_corpus.py --easy 20 --medium 25 --hard 10 --seed 0
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import solve_corpus
from canonical import canonical
from canonical import pad as _pad  # noqa: F401  (re-exported for tests as generate_corpus._pad)
from canonical import rotate90 as _rotate90  # noqa: F401  (re-exported as generate_corpus._rotate90)
from solve_corpus import Solver
from xsb_levels import REPO_ROOT, corpus_xsb, load_corpus, manifest_json, parse_levels

# ``tiers`` lives in the apworld package (the cutoffs the apworld/client share); make it
# importable when this tool runs standalone (the test harness adds it via conftest).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apworld" / "sokopelago"))
import tiers

GENERATOR_VERSION = "1.0.0"

Cell = tuple[int, int]
Rows = tuple[str, ...]
TIER_NAMES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class TierSpec:
    """Construction parameters that *bias* a candidate toward a tier. The real tier comes
    from the scoring solve — these only steer the random construction."""

    w_range: tuple[int, int]  # interior bounding-box width range (incl. walls)
    h_range: tuple[int, int]
    boxes_range: tuple[int, int]
    wall_density: tuple[float, float]  # fraction of interior cells turned to wall
    scatter_range: tuple[int, int]  # number of reverse-pull steps


# Bigger rooms / more boxes / longer scatter -> harder raw signals. Approximate by design.
TIER_SPECS: dict[str, TierSpec] = {
    "easy": TierSpec((5, 7), (5, 7), (1, 2), (0.0, 0.12), (3, 9)),
    "medium": TierSpec((6, 9), (6, 9), (2, 4), (0.04, 0.18), (10, 26)),
    "hard": TierSpec((10, 14), (10, 14), (4, 7), (0.08, 0.24), (55, 110)),
}

# Pre-filter floors: reject obviously-degenerate candidates before the expensive solve.
MIN_PUSH_LB = 2  # solver's matching lower bound on pushes; below this is trivial/solved
MIN_FLOOR = 6  # too few walkable cells -> no real maneuvering

# Candidates scored per round. Fixed (not derived from worker count) so the generated pack
# is identical regardless of ``--workers``: the batch granularity decides when per-tier
# quotas update between rounds, which steers which tier each construction targets. Larger
# rounds also amortize the per-round barrier (a slow hard solve stalls fewer workers).
BATCH_SIZE = 32


# --------------------------------------------------------------------------------------
# Reverse-construction
# --------------------------------------------------------------------------------------
def _largest_component(cells: set[Cell]) -> set[Cell]:
    """Largest 4-connected component of a set of cells (deterministic)."""
    remaining = set(cells)
    best: set[Cell] = set()
    while remaining:
        seed = min(remaining)  # deterministic start
        comp = {seed}
        stack = [seed]
        remaining.discard(seed)
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
                c = (nx, ny)
                if c in remaining:
                    remaining.discard(c)
                    comp.add(c)
                    stack.append(c)
        if len(comp) > len(best):
            best = comp
    return best


def build_room(rng: random.Random, spec: TierSpec) -> tuple[int, int, set[Cell]] | None:
    """Carve a walled room: interior floor minus random interior walls, then keep the
    largest connected region. Returns (width, height, floor cells) or None if degenerate."""
    w = rng.randint(*spec.w_range)
    h = rng.randint(*spec.h_range)
    density = rng.uniform(*spec.wall_density)
    floor: set[Cell] = set()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if rng.random() >= density:
                floor.add((x, y))
    if not floor:
        return None
    comp = _largest_component(floor)
    if len(comp) < MIN_FLOOR:
        return None
    return w, h, comp


def place_solved(rng: random.Random, comp: set[Cell], k: int) -> tuple[set[Cell], set[Cell], Cell] | None:
    """Seed the *solved* state: k boxes each on a goal, plus a player on a free floor cell.
    Leaves headroom (cells beyond boxes+player) so the scatter has somewhere to go."""
    cells = sorted(comp)
    if len(cells) < 3 * k + 2:  # need room to actually scatter the boxes
        return None
    goals = set(rng.sample(cells, k))
    rest = [c for c in cells if c not in goals]
    if not rest:
        return None
    player = rng.choice(rest)
    return goals, set(goals), player  # boxes start on the goals (solved)


def render_xsb(w: int, h: int, comp: set[Cell], goals: set[Cell], boxes: set[Cell], player: Cell) -> Rows:
    """Render a w x h board to XSB rows. Every cell outside ``comp`` is a wall, so the
    region is fully enclosed (no ragged outside padding)."""
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            c = (x, y)
            if c not in comp:
                row.append("#")
            elif c == player:
                row.append("+" if c in goals else "@")
            elif c in boxes:
                row.append("*" if c in goals else "$")
            elif c in goals:
                row.append(".")
            else:
                row.append(" ")
        rows.append("".join(row))
    return tuple(rows)


def scatter(
    rng: random.Random, solver: Solver, player: int, boxes: frozenset[int], steps: int
) -> tuple[int, frozenset[int]]:
    """Scatter boxes off their goals with legal reverse-pulls, in the solver's index space.

    A pull drags a box one cell in direction k with the player leading (player ends one
    cell ahead). Its exact reverse is a forward push, so any state reachable this way from
    the solved state is push-solvable. Pulls are biased to move a box *away* from its
    nearest goal (by lone-box push distance) so the resulting puzzle has a genuinely longer
    optimal solution — purely random pulls tend to cancel out, leaving a short optimum that
    scores easy. Returns the final (player, boxes)."""
    live = set(boxes)
    nbr = solver.neighbour
    ndist = solver.dist  # ndist[g][cell] = pushes to move a lone box from cell to goal g

    def to_goal(cell: int) -> int:
        return min((dm[cell] for dm in ndist), default=0)

    for _ in range(steps):
        reach = solver.reachable(player, frozenset(live))
        options: list[tuple[int, int, int]] = []  # (box, dest, player_end)
        weights: list[float] = []
        for b in sorted(live):
            cur = to_goal(b)
            for k in range(4):
                dest = nbr[b][k]
                if dest == -1 or dest in live or dest not in reach:
                    continue
                player_end = nbr[dest][k]
                if player_end == -1 or player_end in live:
                    continue
                options.append((b, dest, player_end))
                # Favor moves that increase distance-to-goal; allow lateral, rarely closer.
                delta = to_goal(dest) - cur
                weights.append(8.0 if delta > 0 else 2.0 if delta == 0 else 0.5)
        if not options:
            break
        b, dest, player_end = rng.choices(options, weights=weights, k=1)[0]
        live.discard(b)
        live.add(dest)
        player = player_end
    return player, frozenset(live)


def prefilter(solver: Solver, boxes: frozenset[int]) -> bool:
    """Cheap reject of trivial/degenerate candidates *before* solving (reuses the solver's
    matching lower bound). True = worth the expensive scoring solve."""
    if not boxes:
        return False
    if all(b in solver.goal_set for b in boxes):
        return False  # nothing got scattered: already solved
    if len(solver.cells) < MIN_FLOOR:
        return False
    if solver.heuristic(boxes) < MIN_PUSH_LB:
        return False  # boxes essentially on/adjacent to goals: trivial
    return True


def construct_candidate(rng: random.Random, spec: TierSpec) -> Rows | None:
    """One full reverse-construction: room -> solved seed -> scatter -> pre-filter. Returns
    the scattered board's XSB rows (solvable by construction) or None if rejected."""
    room = build_room(rng, spec)
    if room is None:
        return None
    w, h, comp = room
    k = rng.randint(*spec.boxes_range)
    placed = place_solved(rng, comp, k)
    if placed is None:
        return None
    goals, boxes_coord, player_coord = placed
    template = render_xsb(w, h, comp, goals, boxes_coord, player_coord)
    try:
        level = parse_levels("; 1\n\n" + "\n".join(template))[0]
    except (ValueError, IndexError):
        return None
    solver = Solver(level)
    p0 = solver.idx[player_coord]
    b0 = frozenset(solver.idx[b] for b in boxes_coord)
    pf, bf = scatter(rng, solver, p0, b0, rng.randint(*spec.scatter_range))
    if not prefilter(solver, bf):
        return None
    final_boxes = {solver.cells[i] for i in bf}
    return render_xsb(w, h, comp, goals, final_boxes, solver.cells[pf])


# --------------------------------------------------------------------------------------
# Symmetry-aware dedup (8 dihedral transforms)
# --------------------------------------------------------------------------------------
# ``_pad`` / ``_rotate90`` / ``canonical`` now live in the shared ``canonical`` module
# (re-imported above as aliases so this module's public names — and the tests pinning them —
# are unchanged). The cross-corpus seed below stays here because it needs the corpus loader.
def seen_from_corpora(names: tuple[str, ...]) -> set[str]:
    """Canonical forms of every level in the given existing corpora (for cross-corpus
    dedup). Missing corpora are skipped."""
    seen: set[str] = set()
    for name in names:
        path = corpus_xsb(name)
        if not path.exists():
            continue
        for lvl in load_corpus(path):
            seen.add(canonical(lvl.rows))
    return seen


# --------------------------------------------------------------------------------------
# Quality seam: delegated to the standalone, interpretable scorer in ``tools/scoring.py``
# (the same component the corpus annotator uses; a POTD-trained model drops in behind it).
# Used here only to rank within a tier when more candidates survive than the quota.
# --------------------------------------------------------------------------------------
from scoring import score_quality


def _features(result: dict[str, object]) -> dict[str, float]:
    return {
        "par": float(result["par"]),
        "moves": float(result["moves"]),
        "boxes": float(result["boxes"]),
        "search_nodes": float(result["search_nodes"]),
        "difficulty": float(result["difficulty"]),
    }


# --------------------------------------------------------------------------------------
# Parallel scoring (capped solve; node budget is the deterministic gate)
# --------------------------------------------------------------------------------------
def _apply_scoring_caps(node_budget: int) -> None:
    """Configure ``solve_corpus`` for a capped, *deterministic* scoring solve.

    Scoring runs a single optimal-A* phase (weight 1.0) under a node-expansion gate with no
    wall-clock deadline, so the node budget — not machine speed — decides every outcome
    (reproducible across machines). A candidate that doesn't solve push-optimally within the
    budget is, for our purposes, over-budget and discarded; restricting to one phase keeps a
    discard cheap (1x the budget, not 7x across the full coverage ladder) and makes every
    kept level push-optimal. Idempotent. The committed manifest is built with the same caps,
    so its scores match selection exactly."""
    solve_corpus.NODE_BUDGET = node_budget
    solve_corpus.SEARCH_PHASES = ((1.0, 1e9, False),)


def _score_one(rows: Rows, ref_bounds) -> dict[str, object] | None:
    """Solve one candidate (push-only, capped) and attach its calibrated difficulty. Returns
    the scored entry, or None if it didn't solve within the node budget."""
    level = parse_levels("; 1\n\n" + "\n".join(rows))[0]
    entry = solve_corpus.solve(level)
    if not entry.get("solved"):
        return None
    solve_corpus._attach_difficulty([entry], ref_bounds=ref_bounds)
    return {
        "rows": list(rows),
        "par": entry["par"],
        "moves": entry["moves"],
        "boxes": entry["boxes"],
        "search_nodes": entry["search_nodes"],
        "difficulty": entry["difficulty"],
        "solution": entry["solution"],
        "optimal": entry["optimal"],
    }


def _worker(rows: Rows, node_budget: int, ref_bounds, out: mp.Queue) -> None:
    try:
        _apply_scoring_caps(node_budget)
        out.put(_score_one(rows, ref_bounds))
    except Exception:  # a malformed candidate must never crash the run
        out.put(None)


def parallel_score(
    cand_rows: list[Rows], workers: int, node_budget: int, wall_cap: float, ref_bounds
) -> list[dict[str, object] | None]:
    """Score candidates concurrently. The node budget bounds (and makes deterministic) each
    solve; ``wall_cap`` is a per-candidate kill-on-timeout backstop. Results are returned in
    input order, so selection stays reproducible."""
    n = len(cand_rows)
    results: list[dict[str, object] | None] = [None] * n
    if n == 0:
        return results
    if workers <= 1:  # in-process: simplest and fully deterministic (used by tests)
        _apply_scoring_caps(node_budget)
        for i, rows in enumerate(cand_rows):
            try:
                results[i] = _score_one(rows, ref_bounds)
            except Exception:
                results[i] = None
        return results

    ctx = mp.get_context("fork" if hasattr(os, "fork") else "spawn")
    running: dict[int, tuple[mp.Process, mp.Queue, float]] = {}
    nxt = 0
    completed = 0
    while completed < n:
        while len(running) < workers and nxt < n:
            q: mp.Queue = ctx.Queue()
            p = ctx.Process(target=_worker, args=(cand_rows[nxt], node_budget, ref_bounds, q))
            p.start()
            running[nxt] = (p, q, monotonic())
            nxt += 1
        done: list[int] = []
        for i, (p, q, t0) in running.items():
            try:
                results[i] = q.get_nowait()
                p.join(timeout=1)
                done.append(i)
            except queue.Empty:
                if monotonic() - t0 > wall_cap:  # kill-on-timeout backstop
                    p.terminate()
                    p.join(timeout=1)
                    results[i] = None
                    done.append(i)
        for i in done:
            del running[i]
            completed += 1
        if not done:
            time.sleep(0.005)
    return results


# --------------------------------------------------------------------------------------
# Generation loop: construct -> pre-filter -> dedup -> score -> bucket -> keep-to-quota
# --------------------------------------------------------------------------------------
def _under_quota(kept: dict[str, list], quotas: dict[str, int]) -> list[str]:
    return [t for t in TIER_NAMES if len(kept[t]) < quotas.get(t, 0)]


def generate(
    rng: random.Random,
    quotas: dict[str, int],
    *,
    node_budget: int,
    wall_cap: float,
    workers: int,
    ref_bounds,
    seen: set[str],
    attempt_budget: int,
    time_budget: float = 0.0,
    log=lambda *_: None,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, int]]:
    """Run the generate/score/bucket loop until every tier's quota is met, the attempt
    budget is exhausted, or the time budget elapses. Returns (kept-by-tier, stats)."""
    kept: dict[str, list[dict[str, object]]] = {t: [] for t in TIER_NAMES}
    attempts = 0
    scored = 0
    batch_size = BATCH_SIZE
    deadline = monotonic() + time_budget if time_budget else None

    while _under_quota(kept, quotas) and attempts < attempt_budget:
        if deadline and monotonic() > deadline:
            break
        # Build a batch biased toward the still-short tiers (round-robin over them). Tier
        # counts are stable across the batch since scoring happens afterward.
        targets = _under_quota(kept, quotas)
        batch: list[tuple[str, Rows, str]] = []
        while len(batch) < batch_size and attempts < attempt_budget:
            attempts += 1
            tier = targets[len(batch) % len(targets)]
            rows = construct_candidate(rng, TIER_SPECS[tier])
            if rows is None:
                continue
            canon = canonical(rows)
            if canon in seen:
                continue
            seen.add(canon)  # reserve now (dedup within the batch and forever after)
            batch.append((tier, rows, canon))
        if not batch:
            continue

        outcomes = parallel_score([r for _, r, _ in batch], workers, node_budget, wall_cap, ref_bounds)
        for (_target, _rows, canon), result in zip(batch, outcomes, strict=True):
            scored += 1
            if result is None:
                continue  # didn't solve within the budget -> discarded (canon stays blacklisted)
            actual = tiers.tier_of(float(result["difficulty"]))
            if len(kept[actual]) < quotas.get(actual, 0):
                result["canon"] = canon
                result["quality"] = score_quality(_features(result))
                kept[actual].append(result)
        log(
            f"  attempts={attempts} scored={scored} "
            + " ".join(f"{t}={len(kept[t])}/{quotas.get(t, 0)}" for t in TIER_NAMES)
        )

    # Trim any over-quota tier to the best by quality (deterministic tiebreak on canon).
    for t in TIER_NAMES:
        kept[t].sort(key=lambda r: (-float(r["quality"]), r["canon"]))
        kept[t] = kept[t][: quotas.get(t, 0)]
    stats = {"attempts": attempts, "scored": scored, **{t: len(kept[t]) for t in TIER_NAMES}}
    return kept, stats


def ordered_levels(kept: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    """Flatten kept tiers into a single easy->hard difficulty ramp (Microban-style)."""
    flat = [r for t in TIER_NAMES for r in kept[t]]
    flat.sort(key=lambda r: (float(r["difficulty"]), r["canon"]))
    return flat


# --------------------------------------------------------------------------------------
# Emission: write the .xsb, the committed manifest, and the meta sidecar
# --------------------------------------------------------------------------------------
def emit(name: str, levels: list[dict[str, object]], params: dict, *, log=print) -> None:
    """Write ``levels/<name>.xsb``, the committed manifest, and a deterministic meta
    sidecar with provenance.

    The manifest is written *directly* from the optimal scores the generator already
    computed during selection (each via ``solve_corpus.solve`` + ``_attach_difficulty``) —
    it is NOT re-solved through ``solve_corpus``'s full coverage ladder. That ladder's
    per-phase time deadlines would let the optimal phase time out on the hardest levels and
    fall back to a *suboptimal* greedy par (wrong par + node count + difficulty), so a naive
    re-solve would degrade the pack. Emitting from the cached optimal scores keeps every
    level push-optimal and makes the committed manifest exactly the selected one."""
    xsb_path = corpus_xsb(name)
    header = [
        f"; {name} — generated corpus (original by construction; see CREDITS.md)",
        f"; generator v{GENERATOR_VERSION} seed={params['seed']} node_budget={params['node_budget']}",
        "",
    ]
    body: list[str] = []
    entries: list[dict[str, object]] = []
    for n, cand in enumerate(levels, start=1):
        body.append(f"; {n}")
        body.append("")
        body.extend(cand["rows"])
        body.append("")
        entries.append(
            {
                "n": n,
                "name": str(n),
                "par": cand["par"],
                "moves": cand["moves"],
                "solution": cand["solution"],
                "boxes": cand["boxes"],
                "solved": True,
                "optimal": cand["optimal"],
                "difficulty": cand["difficulty"],
                "search_nodes": cand["search_nodes"],
                "board": list(cand["rows"]),
            }
        )
    xsb_path.write_text("\n".join(header + body).rstrip("\n") + "\n", encoding="utf-8")
    log(f"wrote {len(levels)} levels -> {xsb_path.relative_to(REPO_ROOT)}")

    out = manifest_json(name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"wrote manifest -> {out.relative_to(REPO_ROOT)}")

    diffs = [float(c["difficulty"]) for c in levels]
    meta = {
        "generator_version": GENERATOR_VERSION,
        "corpus": name,
        "seed": params["seed"],
        "quotas": params["quotas"],
        "node_budget": params["node_budget"],
        "wall_cap": params["wall_cap"],
        "attempt_budget": params["attempt_budget"],
        "stats": params["stats"],
        "tier_counts": {t: sum(tiers.tier_of(d) == t for d in diffs) for t in TIER_NAMES},
        "difficulty_min": round(min(diffs), 4) if diffs else None,
        "difficulty_max": round(max(diffs), 4) if diffs else None,
    }
    meta_path = REPO_ROOT / "levels" / f"{name}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    log(f"wrote provenance -> {meta_path.relative_to(REPO_ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate an original Sokoban corpus.")
    ap.add_argument("--name", default="autoban", help="corpus name (default: autoban)")
    ap.add_argument("--easy", type=int, default=20, help="easy-tier quota")
    ap.add_argument("--medium", type=int, default=25, help="medium-tier quota")
    ap.add_argument("--hard", type=int, default=10, help="hard-tier quota")
    ap.add_argument("--node-budget", type=int, default=300_000, help="per-solve node cap (the gate)")
    ap.add_argument("--wall-cap", type=float, default=60.0, help="per-solve kill-on-timeout seconds")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=0, help="RNG seed (deterministic pack)")
    ap.add_argument("--attempt-budget", type=int, default=200_000, help="max constructions to try")
    ap.add_argument("--time-budget", type=float, default=0.0, help="wall-clock cap seconds (0=none)")
    args = ap.parse_args()

    quotas = {"easy": args.easy, "medium": args.medium, "hard": args.hard}
    rng = random.Random(args.seed)
    ref_bounds = solve_corpus._calibration_bounds(args.name)
    seen = seen_from_corpora(("microban", "pullban"))

    print(f"generating {args.name}: quotas={quotas} seed={args.seed} workers={args.workers}")
    kept, stats = generate(
        rng,
        quotas,
        node_budget=args.node_budget,
        wall_cap=args.wall_cap,
        workers=args.workers,
        ref_bounds=ref_bounds,
        seen=seen,
        attempt_budget=args.attempt_budget,
        time_budget=args.time_budget,
        log=print,
    )
    levels = ordered_levels(kept)
    for t in TIER_NAMES:
        if len(kept[t]) < quotas[t]:
            print(f"  WARNING: {t} tier under quota: {len(kept[t])}/{quotas[t]}")
    emit(
        args.name,
        levels,
        {
            "seed": args.seed,
            "quotas": quotas,
            "node_budget": args.node_budget,
            "wall_cap": args.wall_cap,
            "attempt_budget": args.attempt_budget,
            "stats": stats,
        },
    )
    print(f"done: {len(levels)} levels (attempts={stats['attempts']}, scored={stats['scored']})")


if __name__ == "__main__":
    main()
