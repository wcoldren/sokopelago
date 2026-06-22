#!/usr/bin/env python3
"""Standalone, interpretable difficulty/"fun" scorer for Sokoban levels.

This is the reusable scoring component: the corpus annotator consumes it now, and the owned
generator's ``score_quality`` seam delegates to it (so a future POTD-trained model can replace
the body behind the same signature without touching either caller).

The scorer is a *transparent, feature-based prior* — grounded in the Sokoban-difficulty and
puzzle-"fun" literature and lightly calibrated on a small human-rated set (see
``tools/calibrate_scoring.py``). It is deliberately **not** a learned oracle: every component
feature is retained alongside the composite, and all weights live in :data:`WEIGHTS` so they can
be inspected and tuned. Reported correlations are a weak sanity check, not proof.

Components, per level (all computable from the existing :class:`solve_corpus.Solver` primitives
plus the persisted solution string — no extra search):

* **box_change_difficulty** — a box-*change* signal: how often the optimal solution switches the
  box it is manipulating (a coupling proxy), blended with search effort and box count. This is a
  proxy *inspired by* Jarušek & Pelánek's problem-decomposition work, not their metric, and we do
  not claim their correlation figures for it.
* **fun_features** — Chu et al. (2025)-style features (playable area, openness, boxes,
  steps-per-box, search difficulty) plus an **inverted-U** likeability: puzzles are most liked at
  moderate-but-achievable challenge, not monotonically "harder = better".
* **structural** — elegance/structure heuristics: goal-room connectedness, fraction of boxes that
  participate in the solution, dead-floor ratio, box density, deadlock proximity.
* **quality_score** — a transparent weighted composite of the above.
"""

from __future__ import annotations

import math

from canonical import canonical_player_normalized_hash
from solve_corpus import DIRS, Solver
from xsb_levels import Level

# --------------------------------------------------------------------------------------
# Tunable weights & reference scales (the calibration seam — fixed by design, lightly tuned)
# --------------------------------------------------------------------------------------
WEIGHTS: dict[str, float] = {
    # box_change_difficulty composite (the four terms sum to 1 -> result already in [0,1])
    "bc_log_count": 0.30,
    "bc_rate": 0.30,
    "bc_nodes": 0.30,
    "bc_boxes": 0.10,
    # inverted-U likeability: challenge blend, then a Gaussian bump over the completion proxy
    "challenge_difficulty": 0.70,
    "challenge_box_change": 0.30,
    "likeability_mu": 0.60,  # peak likeability at completion-proxy 0.60 (moderate challenge)
    "likeability_sigma": 0.22,
    # structural elegance (the four terms sum to 1)
    "elegance_connected": 0.30,
    "elegance_matter": 0.30,
    "elegance_clean": 0.20,
    "elegance_density": 0.20,
    "density_peak": 0.15,  # box density read as "pleasant" around here, decaying either side
    "density_width": 0.15,
    # quality composite (the four terms sum to 1)
    "quality_difficulty": 0.35,
    "quality_box_change": 0.15,
    "quality_likeability": 0.30,
    "quality_structural": 0.20,
}

# Reference scales that map heavy-tailed raw signals into [0,1] (log-compressed first).
C_REF = 20.0  # box-change count at which the log term saturates
NODE_REF = 1e5  # search nodes at which the effort term saturates
BOX_REF = 6.0  # box count at which the box term saturates
MAX_DEADLOCK_STATES = 160  # cap the deadlock-proximity scan on very long solutions


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


# --------------------------------------------------------------------------------------
# Solution tracing (walk the LURD string in the client's board model)
# --------------------------------------------------------------------------------------
def trace_solution(level: Level, solution: str):
    """Replay ``solution`` and return ``(pushed_ids, push_states)``:

    * ``pushed_ids`` — for each push (in order), the identity of the box moved (a stable id
      assigned by start cell), so consecutive entries differing means the solver switched boxes.
    * ``push_states`` — ``(player_cell, frozenset(box_cells))`` after each push, for the
      deadlock-proximity scan.

    Mirrors :func:`solve_corpus.replay`'s movement model (walks lowercase, pushes uppercase,
    ``P<DIR>`` pull units). Assumes a replayable solution (the annotator only scores solved
    levels); stops early on any inconsistency rather than raising.
    """
    delta = dict(DIRS)
    player = level.player
    boxes = set(level.boxes)
    box_id = {cell: i for i, cell in enumerate(sorted(level.boxes))}
    pushed_ids: list[int] = []
    push_states: list[tuple[tuple[int, int], frozenset]] = []

    i = 0
    while i < len(solution):
        ch = solution[i]
        if ch in ("P", "p"):  # pull unit: next char is the shared move direction
            i += 1
            if i >= len(solution):
                break
            dx, dy = delta[solution[i].lower()]
            target = (player[0] + dx, player[1] + dy)
            behind = (player[0] - dx, player[1] - dy)
            if behind not in box_id or target in boxes:
                break
            bid = box_id.pop(behind)
            boxes.discard(behind)
            boxes.add(player)
            box_id[player] = bid
            pushed_ids.append(bid)
            push_states.append((target, frozenset(boxes)))
            player = target
            i += 1
            continue
        dx, dy = delta[ch.lower()]
        target = (player[0] + dx, player[1] + dy)
        if target in boxes:
            beyond = (target[0] + dx, target[1] + dy)
            bid = box_id.pop(target)
            boxes.discard(target)
            boxes.add(beyond)
            box_id[beyond] = bid
            pushed_ids.append(bid)
            player = target
            push_states.append((player, frozenset(boxes)))
        else:
            player = target
        i += 1
    return pushed_ids, push_states


# --------------------------------------------------------------------------------------
# Difficulty: box-change signal
# --------------------------------------------------------------------------------------
def box_change_difficulty(box_switches: int, par: float, nodes: float, boxes: int) -> float:
    """Blend the box-switch count, switch *rate*, search effort, and box count into [0,1].
    Each term is bounded and the weights sum to 1, so the result needs no extra normalization."""
    log_count = clamp01(math.log1p(box_switches) / math.log1p(C_REF))
    rate = clamp01(box_switches / par) if par > 0 else 0.0
    node_term = clamp01(math.log1p(nodes) / math.log1p(NODE_REF))
    box_term = clamp01((boxes - 1) / (BOX_REF - 1))
    return clamp01(
        WEIGHTS["bc_log_count"] * log_count
        + WEIGHTS["bc_rate"] * rate
        + WEIGHTS["bc_nodes"] * node_term
        + WEIGHTS["bc_boxes"] * box_term
    )


# --------------------------------------------------------------------------------------
# Fun features (Chu-style) + inverted-U likeability
# --------------------------------------------------------------------------------------
def openness(solver: Solver) -> float:
    """Mean fraction of a cell's 4 neighbours that are also walkable — the open-room vs
    tight-corridor axis. 1.0 = every cell fully surrounded by floor; ~0.5 = corridors."""
    n = len(solver.cells)
    if n == 0:
        return 0.0
    total = sum(sum(1 for k in range(4) if solver.neighbour[i][k] != -1) for i in range(n))
    return total / (4 * n)


def likeability(challenge: float) -> float:
    """Inverted-U over a completion-rate proxy (``1 - challenge``): liked most at moderate,
    achievable challenge; decays for trivial (proxy->1) and brutal (proxy->0) puzzles."""
    cr_proxy = 1.0 - clamp01(challenge)
    mu, sigma = WEIGHTS["likeability_mu"], WEIGHTS["likeability_sigma"]
    return math.exp(-((cr_proxy - mu) ** 2) / (2 * sigma * sigma))


# --------------------------------------------------------------------------------------
# Structural / elegance heuristics
# --------------------------------------------------------------------------------------
def goal_room_connected(solver: Solver) -> bool:
    """True if the goal cells form a single 4-connected cluster (a coherent 'goal room')."""
    unseen = set(solver.goal_set)
    if len(unseen) <= 1:
        return True
    start = next(iter(unseen))
    unseen.discard(start)
    stack = [start]
    while stack:
        c = stack.pop()
        for k in range(4):
            nb = solver.neighbour[c][k]
            if nb in unseen:
                unseen.discard(nb)
                stack.append(nb)
    return not unseen  # everything reached from one goal -> single component


def deadlock_proximity(solver: Solver, push_states) -> float:
    """Fraction of solution-path positions where the player has at least one *legal* push that
    would freeze an off-goal box (a losing move the solver had to skirt). Capped scan."""
    if not push_states:
        return 0.0
    states = push_states
    if len(states) > MAX_DEADLOCK_STATES:
        stride = len(states) / MAX_DEADLOCK_STATES
        states = [states[int(i * stride)] for i in range(MAX_DEADLOCK_STATES)]
    hits = 0
    for player_cell, box_cells in states:
        boxes_idx = frozenset(solver.idx[c] for c in box_cells)
        region = solver.reachable(solver.idx[player_cell], boxes_idx)
        dangerous = False
        for b in boxes_idx:
            for k in range(4):
                pk = solver.pushes[b][k]
                if pk is None:
                    continue
                target, standing = pk
                if standing in region and target not in boxes_idx:
                    new_boxes = (boxes_idx - {b}) | {target}
                    if solver.freeze_deadlock(target, new_boxes):
                        dangerous = True
                        break
            if dangerous:
                break
        hits += dangerous
    return hits / len(states)


def structural_elegance(connected: bool, matter_fraction: float, dead_ratio: float, density: float) -> float:
    """Transparent [0,1] blend: reward a coherent goal room and solution-relevant boxes, prefer
    little dead floor, and a moderate box density (too sparse or too cramped both read worse)."""
    peak, width = WEIGHTS["density_peak"], WEIGHTS["density_width"]
    density_score = math.exp(-((density - peak) ** 2) / (2 * width * width))
    return clamp01(
        WEIGHTS["elegance_connected"] * (1.0 if connected else 0.0)
        + WEIGHTS["elegance_matter"] * clamp01(matter_fraction)
        + WEIGHTS["elegance_clean"] * (1.0 - clamp01(dead_ratio))
        + WEIGHTS["elegance_density"] * density_score
    )


# --------------------------------------------------------------------------------------
# The seam: composite quality score (pure-dict; the POTD model drops in behind this)
# --------------------------------------------------------------------------------------
def _est_difficulty(features: dict[str, float]) -> float:
    """A cheap difficulty estimate from raw features, for callers (e.g. the generator's hot
    loop) that pass features without a precomputed ``difficulty``."""
    par = features.get("par", 0.0)
    boxes = features.get("boxes", 1.0)
    return clamp01(0.15 + 0.06 * min(boxes, BOX_REF) + 0.03 * min(par, 12.0))


def score_quality(features: dict[str, float]) -> float:
    """0..1 quality/"fun" composite. Works from whatever features it is given: the annotator
    passes the full set (``difficulty``, ``box_change_difficulty``, ``likeability``,
    ``structural_elegance``); the generator's ranking loop passes a thin set and the missing
    components fall back to interpretable defaults. Always clamped to [0,1]."""
    difficulty = float(features.get("difficulty", _est_difficulty(features)))
    box_change = float(features.get("box_change_difficulty", difficulty))
    like = float(features.get("likeability", likeability(difficulty)))
    elegance = float(features.get("structural_elegance", 0.5))
    q = (
        WEIGHTS["quality_difficulty"] * difficulty
        + WEIGHTS["quality_box_change"] * box_change
        + WEIGHTS["quality_likeability"] * like
        + WEIGHTS["quality_structural"] * elegance
    )
    return clamp01(q)


# --------------------------------------------------------------------------------------
# The rich entry point: full feature dict for the annotator
# --------------------------------------------------------------------------------------
def compute_features(level: Level, result: dict, *, solver: Solver | None = None) -> dict:
    """Compute every retained feature + the composite for one level, as the additive manifest
    sub-object. ``result`` is a ``solve_corpus.solve`` entry (par/moves/boxes/search_nodes/
    difficulty/solution/solved). Unsolved levels score from geometry only (difficulty 1.0)."""
    solver = solver or Solver(level)
    solved = bool(result.get("solved"))
    difficulty = float(result.get("difficulty", 1.0))
    boxes = int(result.get("boxes", len(level.boxes)))
    moves = float(result.get("moves", 0.0))
    par = float(result.get("par", 0.0))
    nodes = float(result.get("search_nodes", 0.0))

    area = len(solver.cells)
    spb = moves / max(1, boxes)
    search_diff = clamp01(math.log1p(nodes) / math.log1p(NODE_REF))

    if solved and result.get("solution"):
        pushed_ids, push_states = trace_solution(level, result["solution"])
        switches = sum(1 for i in range(1, len(pushed_ids)) if pushed_ids[i] != pushed_ids[i - 1])
        bc = box_change_difficulty(switches, par, nodes, boxes)
        moved = len({*pushed_ids})
        matter_fraction = moved / max(1, boxes)
        matter_method = "solution-participation"
        dproxy = deadlock_proximity(solver, push_states)
    else:  # geometry-only fallback for unsolved/too-hard levels
        bc = 1.0
        off_goal = sum(1 for b in level.boxes if b not in level.goals)
        matter_fraction = off_goal / max(1, boxes)
        matter_method = "off-goal-start"
        dproxy = 0.0

    challenge = clamp01(
        WEIGHTS["challenge_difficulty"] * difficulty + WEIGHTS["challenge_box_change"] * bc
    )
    like = likeability(challenge)
    connected = goal_room_connected(solver)
    dead_ratio = sum(solver.dead) / max(1, area)
    density = boxes / max(1, area)
    elegance = structural_elegance(connected, matter_fraction, dead_ratio, density)

    quality = score_quality(
        {
            "difficulty": difficulty,
            "box_change_difficulty": bc,
            "likeability": like,
            "structural_elegance": elegance,
            "par": par,
            "boxes": boxes,
        }
    )

    return {
        "box_change_difficulty": round(bc, 4),
        "fun_features": {
            "playable_area": area,
            "openness": round(openness(solver), 4),
            "boxes": boxes,
            "steps_per_box": round(spb, 4),
            "search_difficulty": round(search_diff, 4),
            "likeability": round(like, 4),
        },
        "structural": {
            "goal_room_connected": connected,
            "matter_fraction": round(matter_fraction, 4),
            "matter_method": matter_method,
            "dead_floor_ratio": round(dead_ratio, 4),
            "box_density": round(density, 4),
            "deadlock_proximity": round(dproxy, 4),
        },
        "quality_score": round(quality, 4),
        "canonical_hash": canonical_player_normalized_hash(level),
    }
