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

/** Parse a solution string into directions (case-insensitive; unknown chars ignored). */
export function parseSolution(solution: string): Dir[] {
  const dirs: Dir[] = [];
  for (const ch of solution) {
    const dir = CHAR_TO_DIR[ch.toLowerCase()];
    if (dir) dirs.push(dir);
  }
  return dirs;
}

/** The move at `index` in `moves`, or `null` if out of range. */
export function nextMove(moves: Dir[], index: number): Dir | null {
  return index >= 0 && index < moves.length ? moves[index] : null;
}

/**
 * Realign the board to the solution line and replay its first `count` moves — the
 * mechanic behind a Hint. Restarting first keeps the board on the recorded optimal
 * line regardless of what the player did, so no client-side solver is needed. Returns
 * the number of moves actually applied (clamped to the solution length).
 */
export function replaySolutionPrefix(game: Game, moves: Dir[], count: number): number {
  game.restart();
  const applied = Math.max(0, Math.min(count, moves.length));
  for (let i = 0; i < applied; i++) game.move(moves[i]);
  return applied;
}
