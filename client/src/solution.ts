// Pure helpers for hint playback from a bundled solution string.
//
// The offline solver (tools/solve_corpus.py) records each level's solution as a LURD
// move string (lowercase = walk, UPPERCASE = push). A hint reveals the optimal line
// from the start: the client replays a restart-aligned prefix so the board always
// matches the solution, which avoids needing a client-side solver for arbitrary
// states (we ship none — see ROADMAP). These helpers are server-agnostic and tested.

import type { Dir } from "./types";
import type { Game } from "./board";

const CHAR_TO_DIR: Record<string, Dir> = { u: "up", d: "down", l: "left", r: "right" };

/**
 * One replayable step. `pull` marks the expert pull mechanic; `push` marks a move that
 * shoves a box (uppercase LURD in the solver's encoding). Both are "box-moves" — the units
 * a Hint steps through. A plain walk has both false.
 */
export interface Move {
  dir: Dir;
  pull: boolean;
  push: boolean;
}

/** True if `m` moves a box (a push or a pull) — the granularity Hints reveal. */
export function isBoxMove(m: Move): boolean {
  return m.push || m.pull;
}

/**
 * Parse a solution string into moves (unknown chars ignored). A walk is a lowercase LURD
 * letter; a push is an UPPERCASE LURD letter; a pull is the two-char unit `P<DIR>` (e.g.
 * `PR`) — matching the offline solver's encoding (tools/solve_corpus.py).
 */
export function parseSolution(solution: string): Move[] {
  const moves: Move[] = [];
  for (let i = 0; i < solution.length; i++) {
    const ch = solution[i];
    if (ch === "P" || ch === "p") {
      const dir = CHAR_TO_DIR[solution[i + 1]?.toLowerCase()];
      if (dir) moves.push({ dir, pull: true, push: false });
      i += 1; // consume the direction char
      continue;
    }
    const dir = CHAR_TO_DIR[ch.toLowerCase()];
    // Uppercase LURD = a push (shoves a box); lowercase = a plain walk.
    if (dir) moves.push({ dir, pull: false, push: ch !== ch.toLowerCase() });
  }
  return moves;
}

/** The move at `index` in `moves`, or `null` if out of range. */
export function nextMove(moves: Move[], index: number): Move | null {
  return index >= 0 && index < moves.length ? moves[index] : null;
}

/**
 * Realign the board to the solution line and replay its first `count` moves — the
 * mechanic behind a Hint. Restarting first keeps the board on the recorded optimal
 * line regardless of what the player did, so no client-side solver is needed. Returns
 * the number of moves actually applied (clamped to the solution length).
 */
export function replaySolutionPrefix(game: Game, moves: Move[], count: number): number {
  game.restart();
  const applied = Math.max(0, Math.min(count, moves.length));
  for (let i = 0; i < applied; i++) {
    const m = moves[i];
    if (m.pull) game.pull(m.dir);
    else game.move(m.dir);
  }
  return applied;
}

/**
 * The 1-based move counts at each box-move (push/pull) in `moves`. `boundaries[k-1]` is how
 * many moves to replay to reach the end of the k-th box-move. Length = total box-moves.
 */
export function boxMoveBoundaries(moves: Move[]): number[] {
  const out: number[] = [];
  moves.forEach((m, i) => {
    if (isBoxMove(m)) out.push(i + 1);
  });
  return out;
}

/** The outcome of planning a Hint reveal: how far to animate, and what it costs. */
export interface HintPlan {
  /** Solution moves to animate up to (feed to {@link animateSolutionPrefix}). */
  moveCount: number;
  /** Box-moves now revealed (store as the new hint progress). */
  boxMoves: number;
  /** Hint Tokens this reveal costs (the first box-move is free; the rest cost one each). */
  cost: number;
  /** True when there's nothing new to reveal (already at the last non-winning push). */
  atEnd: boolean;
}

/**
 * Plan a Hint in terms of **box-moves** (pushes/pulls), the natural granularity ("show the
 * first push, then the next…"). Starting from `prevBoxMoves` already revealed, reveal
 * `addBoxMoves` more — but never the final *winning* box-move (that would auto-solve and
 * send the check), so the cap is `totalBoxMoves - 1`. The first box-move is free; each
 * beyond it costs one token. For a single-push level (cap 0) the first hint reveals the walk
 * up to — but not including — that push, for free.
 */
export function planHint(prevBoxMoves: number, addBoxMoves: number, moves: Move[]): HintPlan {
  const boundaries = boxMoveBoundaries(moves);
  const total = boundaries.length;
  const cap = Math.max(0, total - 1); // last box-move is the winning one — off-limits
  const target = Math.min(cap, prevBoxMoves + Math.max(1, addBoxMoves));

  if (target <= prevBoxMoves) {
    // Nothing new among the non-winning pushes. Single-push level: offer the free walk-up
    // to the box on the very first ask, then there's nothing more.
    if (total === 1 && prevBoxMoves === 0) {
      return { moveCount: Math.max(0, boundaries[0] - 1), boxMoves: 0, cost: 0, atEnd: false };
    }
    return {
      moveCount: target >= 1 ? boundaries[target - 1] : 0,
      boxMoves: target,
      cost: 0,
      atEnd: true,
    };
  }

  const moveCount = boundaries[target - 1];
  const cost = Math.max(0, target - Math.max(prevBoxMoves, 1)); // first box-move is free
  return { moveCount, boxMoves: target, cost, atEnd: false };
}

/** Cancel handle for an in-flight {@link animateSolutionPrefix} playback. */
export interface AnimationHandle {
  cancel: () => void;
}

/**
 * Realign the board to the solution line (restart) and animate its first `count` moves,
 * one per `stepMs`, calling `onStep` after the reset and after each applied move (the
 * caller redraws there). Returns a handle whose `cancel()` stops further steps — call it
 * when the level changes so a stale animation can't keep mutating a new board. `onDone`
 * fires after the final step (not on cancel).
 */
export function animateSolutionPrefix(
  game: Game,
  moves: Move[],
  count: number,
  opts: { onStep: () => void; onDone?: () => void; stepMs?: number },
): AnimationHandle {
  const stepMs = opts.stepMs ?? 350;
  const applied = Math.max(0, Math.min(count, moves.length));
  game.restart();
  opts.onStep(); // draw the reset board before the first move
  let i = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancelled = false;
  const tick = (): void => {
    if (cancelled) return;
    if (i >= applied) {
      opts.onDone?.();
      return;
    }
    const m = moves[i];
    if (m.pull) game.pull(m.dir);
    else game.move(m.dir);
    i += 1;
    opts.onStep();
    timer = setTimeout(tick, stepMs);
  };
  timer = setTimeout(tick, stepMs);
  return {
    cancel: () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    },
  };
}
