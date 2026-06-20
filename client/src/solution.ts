// Pure helpers for hint playback from a bundled solution string.
//
// The offline solver (tools/solve_corpus.py) records each level's solution as a LURD
// move string (lowercase = walk, UPPERCASE = push). A hint reveals the optimal line
// from the start: the client replays a restart-aligned prefix so the board always
// matches the solution, which avoids needing a client-side solver for arbitrary
// states (we ship none — see ROADMAP). These helpers are server-agnostic and tested.

import type { Dir } from "./types";

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
