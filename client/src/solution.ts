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

/** One replayable step: a direction plus whether it is a pull (vs walk/push). */
export interface Move {
  dir: Dir;
  pull: boolean;
}

/**
 * Parse a solution string into moves (case-insensitive; unknown chars ignored). Walks
 * and pushes are single LURD letters; a pull is the two-char unit `P<DIR>` (e.g. `PR`),
 * matching the offline solver's encoding (tools/solve_corpus.py).
 */
export function parseSolution(solution: string): Move[] {
  const moves: Move[] = [];
  for (let i = 0; i < solution.length; i++) {
    const ch = solution[i];
    if (ch === "P" || ch === "p") {
      const dir = CHAR_TO_DIR[solution[i + 1]?.toLowerCase()];
      if (dir) moves.push({ dir, pull: true });
      i += 1; // consume the direction char
      continue;
    }
    const dir = CHAR_TO_DIR[ch.toLowerCase()];
    if (dir) moves.push({ dir, pull: false });
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
 * How many solution moves a Hint should have revealed after adding `tierMoves` more,
 * starting from `currentIndex`. Clamped so a Hint never plays the final *winning* move
 * (which would auto-solve the level and send its check) — the cap is `solutionLen - 1`.
 * Returns a count in `[currentIndex, max(0, solutionLen - 1)]`; a result equal to
 * `currentIndex` means there is nothing new to reveal (you're at the final step).
 */
export function revealCount(currentIndex: number, tierMoves: number, solutionLen: number): number {
  const cap = Math.max(0, solutionLen - 1);
  return Math.min(cap, Math.max(currentIndex, currentIndex + tierMoves));
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
  const stepMs = opts.stepMs ?? 280;
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
