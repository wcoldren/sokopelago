#!/usr/bin/env python3
"""Offline data-prep: solve the corpus and write the enriched level manifest.

For every level in ``levels/microban.xsb`` this computes a push-optimal solution
(via A* over box pushes) and expands it to a full move string the client can replay
for hints, then records par / move count / difficulty metrics. The result is written
to ``apworld/sokopelago/data/microban.json`` with one entry per level::

    {"n", "name", "par", "moves", "solution", "boxes", "difficulty", "optimal"}

  * ``par``        — push count of the recorded solution (optimal unless flagged).
  * ``moves``      — length of the expanded move string.
  * ``solution``   — LURD move string (lowercase = walk, UPPERCASE = push),
                     replayable in the client's board model.
  * ``boxes``      — box count (a cheap difficulty signal).
  * ``difficulty`` — normalized 0..1 composite (par/moves/boxes/search-effort),
                     the canonical sort key; raw signals are kept so it can be
                     re-weighted later without re-solving.
  * ``optimal``    — false when a per-level budget forced a non-optimal greedy
                     fallback (a few symmetric levels); the build never fails on it.

The search runs in an index-space fast core (neighbour tables, integer-set box
configs, a memoized minimum-cost-matching heuristic over per-goal wall-aware push
distances) layered with four optimality-preserving prunings/macros:

  * static dead-square pruning (a lone box there can reach no goal),
  * freeze-deadlock detection (a box frozen off-goal can never be recovered),
  * tunnel macros (a run of forced straight pushes through a one-wide corridor is
    collapsed into a single search edge), and
  * PI-corral pruning (when a pushable-inward corral exists, branch only on its
    barrier boxes — the corral theorem keeps this push-optimal).

A* proves optimality where it can within the budget; otherwise greedy best-first finds
a valid (replay-checked) solution so a hint is always available.

A tiny number of Microban levels are beyond this pure-Python search. For those, an
optional build-time fallback shells out to a developer-supplied external solver (set
``SOKO_SOLVER_CMD``) — its output is replay-verified here exactly like a native
solution, so it is never trusted blindly. This stays a developer-local data-prep tool;
no solver binary is vendored or shipped (GPL solvers like JSoko are fine to run this
way).

This is the **offline** half of the project's hard constraint: the generator never
solves Sokoban at generation time; all solvability facts are precomputed here, once,
into the static table both the apworld and client consume.

Run:  python tools/solve_corpus.py

  # With an external solver for the few levels the pure search can't crack. The command
  # receives a temp .xsb path ("{level}" is substituted, else appended) and must print a
  # LURD move string to stdout:
  SOKO_SOLVER_CMD='my-sokoban-solver --lurd {level}' python tools/solve_corpus.py
"""

from __future__ import annotations

import heapq
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from collections import deque

from xsb_levels import REPO_ROOT, Cell, Level, load_corpus

OUT = REPO_ROOT / "apworld" / "sokopelago" / "data" / "microban.json"

# Optional build-time external-solver fallback (data-prep only — never on the generation
# path). When SOKO_SOLVER_CMD is set, levels the pure-Python search can't crack are
# handed to that external process (e.g. a developer's local Sokolution/JSoko build). The
# command is run once per such level; "{level}" in it is replaced with a temp .xsb path
# (otherwise the path is appended), and the process must print a LURD move string to
# stdout. Whatever it returns is replay-verified here exactly like a native solution, so
# a wrong/garbled answer is rejected, never trusted. GPL solvers (JSoko) are fine to run
# locally this way; we never vendor or ship their binaries.
SOLVER_CMD_ENV = "SOKO_SOLVER_CMD"
SOLVER_TIMEOUT_ENV = "SOKO_SOLVER_TIMEOUT"  # seconds; default 300
_LURD_RUN = re.compile(r"[lrudLRUD]{4,}")

# (letter, dx, dy) per direction, matching client DELTA (origin top-left, +y down).
DIRS: tuple[tuple[str, Cell], ...] = (("u", (0, -1)), ("d", (0, 1)), ("l", (-1, 0)), ("r", (1, 0)))

NODE_BUDGET = 6_000_000  # per phase
# Search phases tried in order: (heuristic weight, seconds, use_corral). weight 1 =
# optimal A*; weights slightly above 1 are bounded-suboptimal but dramatically faster
# on highly-symmetric levels (where pure A* drowns in equivalent states and greedy gets
# lost); None = greedy best-first. The first phase that finds a solution wins; only
# weight 1 is recorded as optimal.
#
# The pure (use_corral=False) phases run first and are exactly the sound
# freeze/tunnel/dead-square solver, so they fix every level's optimal par and coverage.
# PI-corral pruning is a powerful but not-provably-sound hard prune (a corral can
# "flip"), so it is enabled only in the two trailing last-resort phases that run *after*
# the pure phases have failed — it can crack levels the pure search can't while never
# costing coverage or corrupting an ``optimal`` par.
SEARCH_PHASES: tuple[tuple[float | None, float, bool], ...] = (
    (1.0, 15.0, False),
    (1.3, 40.0, False),
    (1.7, 40.0, False),
    (2.5, 40.0, False),
    (None, 40.0, False),
    (2.5, 25.0, True),
    (None, 25.0, True),
)
UNREACHABLE = 1_000_000  # sentinel push-distance for a cell that can reach no goal


def hungarian(cost: list[list[int]]) -> int:
    """Minimum-cost perfect matching of a square cost matrix (O(n^3) assignment)."""
    n = len(cost)
    if n == 0:
        return 0
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [1 << 60] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = 1 << 60
            j1 = -1
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    total = 0
    for j in range(1, n + 1):
        total += cost[p[j] - 1][j - 1]
    return total


class Solver:
    """Index-space Sokoban solver for one level.

    Walkable cells are numbered 0..N-1; box configurations are ``frozenset[int]``.
    Precomputes neighbour tables, per-goal push-distance maps, dead squares, and the
    legal pushes from each cell so the A*/greedy inner loop stays cheap.
    """

    def __init__(self, level: Level) -> None:
        self.level = level
        self.cells: list[Cell] = sorted(level.walkable)  # sorted -> min index is canonical
        self.idx: dict[Cell, int] = {c: i for i, c in enumerate(self.cells)}
        n = len(self.cells)

        # neighbour[i][k] = walkable cell index in direction k, or -1.
        self.neighbour: list[list[int]] = [[-1, -1, -1, -1] for _ in range(n)]
        for i, (x, y) in enumerate(self.cells):
            for k, (_, (dx, dy)) in enumerate(DIRS):
                self.neighbour[i][k] = self.idx.get((x + dx, y + dy), -1)

        self.goals: list[int] = [self.idx[g] for g in sorted(level.goals)]
        self.goal_set: frozenset[int] = frozenset(self.goals)

        # dist[g][i] = min pushes to move a lone box from cell i to goal g (else UNREACHABLE).
        self.dist: list[list[int]] = [self._goal_distances(g) for g in self.goals]
        self.dead: list[bool] = [all(dm[i] >= UNREACHABLE for dm in self.dist) for i in range(n)]

        # pushes[b][k] = (target idx, standing idx) for pushing the box at b in dir k,
        # or None when the push is statically impossible (off-board or into a dead cell).
        self.pushes: list[list[tuple[int, int] | None]] = []
        for i in range(n):
            row: list[tuple[int, int] | None] = []
            for k in range(4):
                target = self.neighbour[i][k]
                standing = self.neighbour[i][k ^ 1]  # opposite dir (u<->d, l<->r)
                if target == -1 or standing == -1 or self.dead[target]:
                    row.append(None)
                else:
                    row.append((target, standing))
            self.pushes.append(row)

        # tunnel[c] = (horizontal_corridor, vertical_corridor): a box at c can only be
        # pushed along one axis because the perpendicular neighbours are both walls.
        # [0] True -> up/down are walls (a horizontal corridor); [1] -> left/right walls.
        self.tunnel: list[tuple[bool, bool]] = [
            (
                self.neighbour[i][0] == -1 and self.neighbour[i][1] == -1,
                self.neighbour[i][2] == -1 and self.neighbour[i][3] == -1,
            )
            for i in range(n)
        ]

        self.start_player = self.idx[level.player]
        self.start_boxes: frozenset[int] = frozenset(self.idx[b] for b in level.boxes)
        self._h_cache: dict[frozenset[int], int] = {}

    # --- Deadlock detection ------------------------------------------------

    def _blocked(self, cell: int, boxes: frozenset[int], axis: int, walls: set[int]) -> bool:
        """Is the box at ``cell`` immovable along ``axis`` (0=horizontal, 1=vertical)?

        Blocked when either neighbour along the axis is a wall (or a box already being
        evaluated, treated as a wall to break recursion), both neighbours are simple
        dead squares, or a neighbour box is itself blocked along the *other* axis. This
        is the standard recursive freeze test from the Sokoban deadlock literature.
        """
        ka, kb = (2, 3) if axis == 0 else (0, 1)
        a = self.neighbour[cell][ka]
        b = self.neighbour[cell][kb]
        if a == -1 or b == -1 or a in walls or b in walls:
            return True
        if self.dead[a] and self.dead[b]:
            return True
        walls.add(cell)  # treat this box as a wall while probing its neighbours
        result = (a in boxes and self._blocked(a, boxes, 1 - axis, walls)) or (
            b in boxes and self._blocked(b, boxes, 1 - axis, walls)
        )
        walls.discard(cell)
        return result

    def _box_frozen(self, cell: int, boxes: frozenset[int]) -> bool:
        """True iff the box at ``cell`` can never move again (blocked on both axes)."""
        return self._blocked(cell, boxes, 0, set()) and self._blocked(cell, boxes, 1, set())

    def freeze_deadlock(self, cell: int, boxes: frozenset[int]) -> bool:
        """True if the just-pushed box at ``cell`` froze a cluster holding an off-goal box.

        A frozen box can never move, so if any box in its mutually-frozen cluster sits
        off a goal the position is unwinnable. Off-goal boxes that are still movable are
        fine; a frozen cluster entirely on goals is fine (often it is part of the win).
        """
        if not self._box_frozen(cell, boxes):
            return False
        stack = [cell]
        seen = {cell}
        while stack:
            c = stack.pop()
            if c not in self.goal_set:
                return True
            for k in range(4):
                nb = self.neighbour[c][k]
                if nb != -1 and nb in boxes and nb not in seen and self._box_frozen(nb, boxes):
                    seen.add(nb)
                    stack.append(nb)
        return False

    def pi_corral(self, region: set[int], boxes: frozenset[int]) -> set[int] | None:
        """Return a PI-corral's barrier boxes to restrict branching to, or None.

        A *corral* is a connected component of floor the player cannot reach. It is a
        *PI-corral* (pushable-inward) when every push the player can currently make to a
        barrier box drives it into the corral — never out or along it. The corral
        theorem then says some solution's next push enters it, so branching only on its
        barrier boxes prunes the rest of the frontier.

        This is the classic I-corral test and it is a powerful accelerator, but as a
        *hard* prune in a closed-set search it is not always sound: a corral can "flip"
        (after pushing boxes in, the player follows and a barrier box that looked
        inward-only can be pushed back out), which can cut the only solution. So it is
        enabled only in the two trailing last-resort phases that run *after* the pure,
        corral-free phases have already established each level's coverage and optimal par
        (see ``SEARCH_PHASES``/``solve``). It can therefore crack a stubborn level the
        pure search couldn't, but can never cost coverage or corrupt an ``optimal`` par.
        """
        n = len(self.cells)
        nbr = self.neighbour
        seen: set[int] = set()
        for c in range(n):
            if c in region or c in boxes or c in seen:
                continue
            comp = {c}
            stack = [c]
            seen.add(c)
            barrier: set[int] = set()
            while stack:
                x = stack.pop()
                for k in range(4):
                    y = nbr[x][k]
                    if y == -1:
                        continue
                    if y in boxes:
                        barrier.add(y)
                    elif y not in region and y not in seen:
                        seen.add(y)
                        comp.add(y)
                        stack.append(y)
            inward_only = True
            inward_now = False
            for b in barrier:
                for k in range(4):
                    target = nbr[b][k]
                    standing = nbr[b][k ^ 1]
                    if target == -1 or standing == -1 or standing not in region or target in boxes:
                        continue  # not a push the player can make right now
                    if target in comp:
                        inward_now = True
                    else:
                        inward_only = False  # a current push that escapes the corral
                        break
                if not inward_only:
                    break
            if inward_only and inward_now:
                return barrier
        return None

    def _goal_distances(self, goal: int) -> list[int]:
        n = len(self.cells)
        dist = [UNREACHABLE] * n
        dist[goal] = 0
        queue = deque([goal])
        while queue:
            c = queue.popleft()
            for k in range(4):
                # reverse push: a box at `c` could have come from `prev`, pushed toward c,
                # which needs `prev` (its old cell) and `beyond` (where the pusher stood).
                prev = self.neighbour[c][k]
                if prev == -1:
                    continue
                beyond = self.neighbour[prev][k]
                if beyond == -1 or dist[prev] != UNREACHABLE:
                    continue
                dist[prev] = dist[c] + 1
                queue.append(prev)
        return dist

    def reachable(self, start: int, boxes: frozenset[int]) -> set[int]:
        seen = {start}
        queue = deque((start,))
        nbr = self.neighbour
        while queue:
            c = queue.popleft()
            for k in range(4):
                nxt = nbr[c][k]
                if nxt != -1 and nxt not in boxes and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def normalize(self, player: int, boxes: frozenset[int]) -> int:
        return min(self.reachable(player, boxes))

    def heuristic(self, boxes: frozenset[int]) -> int:
        cached = self._h_cache.get(boxes)
        if cached is not None:
            return cached
        box_list = sorted(boxes)
        cost = [[dm[b] for dm in self.dist] for b in box_list]
        h = hungarian(cost)
        self._h_cache[boxes] = h
        return h

    def bfs_path(self, start: int, goal: int, boxes: frozenset[int]) -> list[int]:
        """Shortest walk from cell ``start`` to ``goal`` as a list of direction indices."""
        if start == goal:
            return []
        prev: dict[int, tuple[int, int]] = {}
        seen = {start}
        queue = deque((start,))
        nbr = self.neighbour
        while queue:
            c = queue.popleft()
            for k in range(4):
                nxt = nbr[c][k]
                if nxt != -1 and nxt not in boxes and nxt not in seen:
                    seen.add(nxt)
                    prev[nxt] = (c, k)
                    if nxt == goal:
                        path: list[int] = []
                        cur = nxt
                        while cur != start:
                            pc, pk = prev[cur]
                            path.append(pk)
                            cur = pc
                        path.reverse()
                        return path
                    queue.append(nxt)
        raise ValueError(f"no walk path from {start} to {goal}")


# A push edge: (standing idx, direction index, push count, player-after idx, new box
# config). ``count`` > 1 when a tunnel macro collapsed a run of forced straight pushes.
PushEdge = tuple[int, int, int, int, frozenset[int]]
State = tuple[int, frozenset[int]]

# A move edge for the pull-aware search: (walk-to idx, direction index, box-move count,
# player-after idx, new box config, is_pull). Pushes and pulls both move a box one cell
# in ``direction``; they differ in where the player stands to do it and ends up.
MoveEdge = tuple[int, int, int, int, frozenset[int], bool]


def _search(
    solver: Solver, weight: float | None, time_budget: float, use_corral: bool = False
) -> tuple[list[PushEdge], int] | None:
    """Best-first search over pushes.

    ``weight`` scales the heuristic in the priority: 1.0 = optimal A*, >1 =
    bounded-suboptimal (faster), None = greedy best-first. ``use_corral`` turns on
    PI-corral branch pruning (only safe to enable when the caller is willing to retry
    without it — see ``solve``). Returns (edges, nodes) or None if no solution is found
    within the node/time budget.
    """
    if solver.start_boxes == solver.goal_set:
        return [], 0

    start: State = (solver.normalize(solver.start_player, solver.start_boxes), solver.start_boxes)
    g_score: dict[State, int] = {start: 0}
    came: dict[State, tuple[State, PushEdge]] = {}
    h_start = solver.heuristic(solver.start_boxes)
    open_heap: list[tuple[float, int, State]] = [(h_start, 0, start)]
    closed: set[State] = set()
    counter = 0
    nodes = 0
    deadline = time.monotonic() + time_budget

    while open_heap:
        _, _, state = heapq.heappop(open_heap)
        if state in closed:
            continue
        closed.add(state)
        nodes += 1
        if nodes > NODE_BUDGET or ((nodes & 0x3FFF) == 0 and time.monotonic() > deadline):
            return None
        player_norm, boxes = state
        if boxes == solver.goal_set:
            edges: list[PushEdge] = []
            cur = state
            while cur in came:
                prev, edge = came[cur]
                edges.append(edge)
                cur = prev
            edges.reverse()
            return edges, nodes
        g = g_score[state]
        region = solver.reachable(player_norm, boxes)
        # PI-corral pruning (sub-optimal phases only): if a pushable-inward corral
        # exists, branch only on its barrier boxes. Guarded by a retry in solve().
        corral = solver.pi_corral(region, boxes) if use_corral else None
        box_iter = corral if corral is not None else boxes
        for b in box_iter:
            for k in range(4):
                push = solver.pushes[b][k]
                if push is None:
                    continue
                target, standing = push
                if target in boxes or standing not in region:
                    continue
                # The elementary one-cell push is always offered (keeps the search
                # complete). Tunnel macro: while the box sits in a one-wide corridor
                # along this axis (and not on a goal), pushing straight on is forced, so
                # we *additionally* offer a shortcut edge that collapses the whole run —
                # an accelerator that never removes the intermediate stops, because a box
                # parked mid-corridor can still be a needed blocker.
                axis = 0 if k >= 2 else 1
                dests = [(target, 1, b)]  # (box cell, push count, player-after cell)
                box_cell, player_after, count = target, b, 1
                while box_cell not in solver.goal_set and solver.tunnel[box_cell][axis]:
                    nxt_cell = solver.neighbour[box_cell][k]
                    if nxt_cell == -1 or nxt_cell in boxes or solver.dead[nxt_cell]:
                        break
                    player_after, box_cell, count = box_cell, nxt_cell, count + 1
                if count > 1:
                    dests.append((box_cell, count, player_after))
                for dest, push_count, pa in dests:
                    new_boxes = (boxes - {b}) | {dest}
                    if solver.freeze_deadlock(dest, new_boxes):
                        continue
                    ng = g + push_count
                    nxt_norm = solver.normalize(pa, new_boxes)
                    nxt: State = (nxt_norm, new_boxes)
                    if nxt in closed or ng >= g_score.get(nxt, 1 << 30):
                        continue
                    h = solver.heuristic(new_boxes)
                    if h >= UNREACHABLE:
                        continue  # a box landed in a matching deadlock
                    g_score[nxt] = ng
                    came[nxt] = (state, (standing, k, push_count, pa, new_boxes))
                    counter += 1
                    priority = float(h) if weight is None else ng + weight * h
                    heapq.heappush(open_heap, (priority, counter, nxt))
    return None


def _reconstruct(solver: Solver, edges: list[PushEdge]) -> str:
    """Expand push edges into a concrete move string from the level's player start."""
    player = solver.start_player
    boxes = solver.start_boxes
    moves: list[str] = []
    for standing, k, count, player_after, new_boxes in edges:
        moves.extend(DIRS[step][0] for step in solver.bfs_path(player, standing, boxes))  # walks (lowercase)
        moves.append(DIRS[k][0].upper() * count)  # one or more straight pushes (uppercase)
        player = player_after
        boxes = new_boxes
    return "".join(moves)


def replay(level: Level, solution: str) -> bool:
    """Replay a move string in the client's board model; True iff it solves the level.

    Walks are lowercase LURD, pushes uppercase LURD, and a *pull* is a two-char unit
    ``P<DIR>`` (e.g. ``PR``): the player steps one cell in ``DIR`` and a box directly
    behind (opposite ``DIR``) follows into the player's vacated cell. Pull units appear
    only in expert-corpus solutions; pure push/walk strings replay unchanged.
    """
    delta = dict(DIRS)
    player = level.player
    boxes = set(level.boxes)
    i = 0
    while i < len(solution):
        ch = solution[i]
        if ch in ("P", "p"):  # pull: the next char is the player's (and box's) move dir
            i += 1
            if i >= len(solution):
                return False
            dx, dy = delta[solution[i].lower()]
            target = (player[0] + dx, player[1] + dy)  # player destination
            behind = (player[0] - dx, player[1] - dy)  # box must be directly behind
            if target not in level.walkable or target in boxes or behind not in boxes:
                return False
            boxes.discard(behind)
            boxes.add(player)  # box follows into the player's old cell
            player = target
            i += 1
            continue
        dx, dy = delta[ch.lower()]
        target = (player[0] + dx, player[1] + dy)
        if target not in level.walkable:
            return False
        if target in boxes:
            beyond = (target[0] + dx, target[1] + dy)
            if beyond not in level.walkable or beyond in boxes:
                return False
            boxes.discard(target)
            boxes.add(beyond)
        player = target
        i += 1
    return boxes == set(level.goals)


def _level_to_xsb(level: Level) -> str:
    """Render a level back to a clean, fully-bordered rectangular XSB block.

    Every non-walkable cell (including the ragged outside) becomes a wall, so the board
    is a solid rectangle that even strict external parsers accept.
    """
    xs = [x for x, _ in level.walkable]
    ys = [y for _, y in level.walkable]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    rows: list[str] = []
    for y in range(y0, y1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            cell = (x, y)
            is_goal = cell in level.goals
            if cell == level.player:
                row.append("+" if is_goal else "@")
            elif cell in level.boxes:
                row.append("*" if is_goal else "$")
            elif is_goal:
                row.append(".")
            elif cell in level.walkable:
                row.append(" ")
            else:
                row.append("#")
        rows.append("".join(row))
    return "\n".join(rows) + "\n"


def _external_solve(level: Level) -> str | None:
    """Last-resort: shell out to a developer-configured external solver (data-prep only).

    Returns a replay-verified LURD solution, or None if no solver is configured, it
    fails/times out, or its output does not actually solve the level. Never raises.
    """
    command = os.environ.get(SOLVER_CMD_ENV)
    if not command:
        return None
    try:
        timeout = float(os.environ.get(SOLVER_TIMEOUT_ENV, "300"))
    except ValueError:
        timeout = 300.0
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"microban_{level.n}.xsb")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_level_to_xsb(level))
        argv = shlex.split(command)
        argv = [path if tok == "{level}" else tok for tok in argv]
        if "{level}" not in command:
            argv.append(path)
        try:
            # argv is developer-configured (SOKO_SOLVER_CMD); data-prep only.
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=tmp, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
    # Try each LURD-looking run in the output (longest first); accept the first that wins.
    candidates = sorted(_LURD_RUN.findall(proc.stdout), key=len, reverse=True)
    for cand in candidates:
        if replay(level, cand):
            return cand
    return None


def solve(level: Level) -> dict[str, object]:
    """Solve one level and return its enriched manifest entry (without difficulty).

    The pure-Python search runs first; if it is exhausted, an optional external solver
    (``SOKO_SOLVER_CMD``) is tried. Any level still unsolved is returned with
    ``solved=False`` and no par/solution — it simply has no in-client hint, and the Skip
    Token is the player's escape valve for any level they (or the solver) can't crack.
    """
    solver = Solver(level)
    result: tuple[list[PushEdge], int] | None = None
    optimal = False
    for weight, time_budget, use_corral in SEARCH_PHASES:
        result = _search(solver, weight, time_budget, use_corral)
        if result is not None:
            optimal = weight == 1.0
            break

    if result is not None:
        edges, nodes = result
        solution = _reconstruct(solver, edges)
        if not replay(level, solution):
            raise SystemExit(f"level {level.n}: reconstructed solution does not replay to a win")
        par = sum(count for _, _, count, _, _ in edges)  # total pushes (macros count each push)
        return {
            "n": level.n,
            "name": level.name,
            "par": par,
            "moves": len(solution),
            "solution": solution,
            "boxes": len(level.boxes),
            "_nodes": nodes,  # raw search-effort signal; dropped after normalization
            "solved": True,
            "optimal": optimal,
        }

    external = _external_solve(level)
    if external is not None:
        return {
            "n": level.n,
            "name": level.name,
            "par": sum(ch.isupper() for ch in external),  # uppercase moves are pushes
            "moves": len(external),
            "solution": external,
            "boxes": len(level.boxes),
            "_nodes": NODE_BUDGET,  # hardest tier: beyond the native search budget
            "solved": True,
            "optimal": False,
            "solver": "external",  # provenance: not from the native push-optimal search
        }

    return {"n": level.n, "name": level.name, "boxes": len(level.boxes), "solved": False, "optimal": False}


PULL_NODE_BUDGET = 2_000_000  # expert corpora are small, hand-authored levels


def _search_pull(solver: Solver, time_budget: float) -> tuple[list[MoveEdge], int] | None:
    """Uniform-cost (Dijkstra) search over BOTH pushes and pulls; optimal box-move count.

    A *pull* moves a box one cell in direction ``k`` with the player ahead of it (the
    player steps in ``k`` and the box follows into the player's vacated cell). Pulls make
    otherwise-unsolvable configurations solvable, so the push-only soundness prunings
    (static dead squares, freeze-deadlock) are deliberately NOT applied here — a box on a
    push-"dead" square may be pullable out. Authored expert levels are tiny, so the plain
    closed-set search is fast enough without them. Returns (edges, nodes) or None.
    """
    if solver.start_boxes == solver.goal_set:
        return [], 0

    start: State = (solver.normalize(solver.start_player, solver.start_boxes), solver.start_boxes)
    g_score: dict[State, int] = {start: 0}
    came: dict[State, tuple[State, MoveEdge]] = {}
    open_heap: list[tuple[int, int, State]] = [(0, 0, start)]
    closed: set[State] = set()
    counter = 0
    nodes = 0
    nbr = solver.neighbour
    deadline = time.monotonic() + time_budget

    while open_heap:
        g, _, state = heapq.heappop(open_heap)
        if state in closed:
            continue
        closed.add(state)
        nodes += 1
        if nodes > PULL_NODE_BUDGET or ((nodes & 0x3FFF) == 0 and time.monotonic() > deadline):
            return None
        player_norm, boxes = state
        if boxes == solver.goal_set:
            edges: list[MoveEdge] = []
            cur = state
            while cur in came:
                prev, edge = came[cur]
                edges.append(edge)
                cur = prev
            edges.reverse()
            return edges, nodes
        region = solver.reachable(player_norm, boxes)
        successors: list[MoveEdge] = []
        for b in boxes:
            for k in range(4):
                dest = nbr[b][k]  # box destination (one cell in dir k); same for push & pull
                if dest == -1 or dest in boxes:
                    continue
                new_boxes = (boxes - {b}) | {dest}
                standing = nbr[b][k ^ 1]  # push: player behind, ends on the box's old cell
                if standing != -1 and standing in region:
                    successors.append((standing, k, 1, b, new_boxes, False))
                if dest in region:  # pull: player stands on `dest`, steps to `dest + k`
                    player_end = nbr[dest][k]
                    if player_end != -1 and player_end not in boxes:
                        successors.append((dest, k, 1, player_end, new_boxes, True))
        for walk_to, k, count, pa, new_boxes, is_pull in successors:
            ng = g + count
            nxt_norm = solver.normalize(pa, new_boxes)
            nxt: State = (nxt_norm, new_boxes)
            if nxt in closed or ng >= g_score.get(nxt, 1 << 30):
                continue
            g_score[nxt] = ng
            came[nxt] = (state, (walk_to, k, count, pa, new_boxes, is_pull))
            counter += 1
            heapq.heappush(open_heap, (ng, counter, nxt))
    return None


def _reconstruct_pull(solver: Solver, edges: list[MoveEdge]) -> str:
    """Expand pull-aware move edges into a concrete move string from the player start."""
    player = solver.start_player
    boxes = solver.start_boxes
    moves: list[str] = []
    for walk_to, k, count, player_after, new_boxes, is_pull in edges:
        moves.extend(DIRS[step][0] for step in solver.bfs_path(player, walk_to, boxes))  # walks
        if is_pull:
            moves.append("P" + DIRS[k][0].upper())  # a single-cell pull
        else:
            moves.append(DIRS[k][0].upper() * count)  # push(es)
        player = player_after
        boxes = new_boxes
    return "".join(moves)


def push_solvable(level: Level) -> bool:
    """True iff the level has a pure push-only solution (no external solver, no pulls)."""
    solver = Solver(level)
    return any(_search(solver, w, t, c) is not None for w, t, c in SEARCH_PHASES)


def solve_pull(level: Level, time_budget: float = 30.0) -> dict[str, object]:
    """Solve one level allowing pulls, tagging whether it *requires* a pull.

    ``requires_pull`` is True when no push-only solution exists but a pull-aware one does
    — i.e. the level is genuinely gated behind the Pull ability. Mirrors ``solve``'s entry
    shape (par/moves/solution/boxes/difficulty inputs) so ``_attach_difficulty`` works."""
    solver = Solver(level)
    result = _search_pull(solver, time_budget)
    needs_pull = not push_solvable(level)
    if result is None:
        return {
            "n": level.n,
            "name": level.name,
            "boxes": len(level.boxes),
            "solved": False,
            "optimal": False,
            "requires_pull": needs_pull,
        }
    edges, nodes = result
    solution = _reconstruct_pull(solver, edges)
    if not replay(level, solution):
        raise SystemExit(f"level {level.n}: reconstructed pull solution does not replay to a win")
    return {
        "n": level.n,
        "name": level.name,
        "par": len(edges),  # box-moves (pushes + pulls)
        "moves": len(solution),
        "solution": solution,
        "boxes": len(level.boxes),
        "_nodes": nodes,
        "solved": True,
        "optimal": True,  # uniform-cost over push+pull -> minimal box-move count
        "requires_pull": needs_pull,
    }


def _normalized(value: float, lo: float, hi: float) -> float:
    return 0.0 if hi <= lo else (value - lo) / (hi - lo)


def _attach_difficulty(entries: list[dict[str, object]]) -> None:
    """Add a normalized 0..1 ``difficulty`` blend across the corpus, in place.

    Normalization spans the solved levels; any level the solver couldn't crack is, by
    definition, among the hardest, so it is assigned the max difficulty (1.0)."""
    solved = [e for e in entries if e.get("solved")]
    signals = ("par", "moves", "boxes", "_nodes")
    bounds = {s: (min(float(e[s]) for e in solved), max(float(e[s]) for e in solved)) for s in signals}
    weights = {"par": 0.4, "moves": 0.2, "boxes": 0.2, "_nodes": 0.2}
    for e in entries:
        if e.get("solved"):
            score = sum(weights[s] * _normalized(float(e[s]), *bounds[s]) for s in signals)
            e["difficulty"] = round(score, 4)
            del e["_nodes"]
        else:
            e["difficulty"] = 1.0


def main() -> None:
    levels = load_corpus()
    entries: list[dict[str, object]] = []
    for level in levels:
        entry = solve(level)
        entries.append(entry)
        status = f"par={entry['par']} optimal={entry['optimal']}" if entry.get("solved") else "UNSOLVED (no hint)"
        print(f"  level {level.n}: {status}", flush=True)
    _attach_difficulty(entries)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    non_optimal = [e["n"] for e in entries if e.get("solved") and not e["optimal"]]
    unsolved = [e["n"] for e in entries if not e.get("solved")]
    print(f"solved {len(entries) - len(unsolved)}/{len(entries)} levels -> {OUT.relative_to(REPO_ROOT)}")
    if non_optimal:
        print(f"  note: non-optimal greedy fallback used for levels: {non_optimal}")
    if unsolved:
        print(f"  note: no solution found (no hint available) for levels: {unsolved}")


if __name__ == "__main__":
    main()
