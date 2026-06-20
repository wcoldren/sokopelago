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
