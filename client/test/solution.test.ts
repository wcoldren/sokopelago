import { describe, expect, it } from "vitest";

import {
  boxMoveBoundaries,
  nextMove,
  parseSolution,
  planHint,
  replaySolutionPrefix,
} from "../src/solution";
import { parseXsb } from "../src/xsb";
import { Game } from "../src/board";

// A one-line level: player, a gap, a box, then its goal. Solution "rr" = walk right,
// then push the box onto the goal.
const SOLVABLE = ["######", "#@ $.#", "######"].join("\n");
const game = (): Game => new Game(parseXsb(SOLVABLE)[0]);

describe("solution — parseSolution", () => {
  it("maps LURD to directions; UPPERCASE marks a push, lowercase a walk", () => {
    expect(parseSolution("uDlR")).toEqual([
      { dir: "up", pull: false, push: false },
      { dir: "down", pull: false, push: true },
      { dir: "left", pull: false, push: false },
      { dir: "right", pull: false, push: true },
    ]);
  });

  it("parses a P<DIR> unit as a pull move (not a push)", () => {
    expect(parseSolution("rPRd")).toEqual([
      { dir: "right", pull: false, push: false },
      { dir: "right", pull: true, push: false },
      { dir: "down", pull: false, push: false },
    ]);
  });

  it("ignores characters that are not move letters", () => {
    expect(parseSolution("u x d!")).toEqual([
      { dir: "up", pull: false, push: false },
      { dir: "down", pull: false, push: false },
    ]);
  });

  it("returns an empty list for an empty string", () => {
    expect(parseSolution("")).toEqual([]);
  });
});

describe("solution — nextMove", () => {
  it("returns the move at the index", () => {
    const moves = parseSolution("urd");
    expect(nextMove(moves, 0)).toEqual({ dir: "up", pull: false, push: false });
    expect(nextMove(moves, 2)).toEqual({ dir: "down", pull: false, push: false });
  });

  it("returns null out of range", () => {
    const moves = parseSolution("ur");
    expect(nextMove(moves, -1)).toBeNull();
    expect(nextMove(moves, 2)).toBeNull();
  });
});

describe("solution — replaySolutionPrefix", () => {
  const moves = parseSolution("rr");

  it("replays the first N moves from the start", () => {
    const g = game();
    expect(replaySolutionPrefix(g, moves, 1)).toBe(1);
    expect(g.player).toEqual({ x: 2, y: 1 }); // walked right; box not yet pushed
    expect(g.boxAt(3, 1)).toBe(true);
    expect(g.isWin()).toBe(false);
  });

  it("replaying the whole solution wins the level", () => {
    const g = game();
    expect(replaySolutionPrefix(g, moves, 2)).toBe(2);
    expect(g.boxAt(4, 1)).toBe(true); // pushed onto the goal
    expect(g.isWin()).toBe(true);
  });

  it("clamps the count to the solution length", () => {
    const g = game();
    expect(replaySolutionPrefix(g, moves, 99)).toBe(2);
    expect(g.isWin()).toBe(true);
  });

  it("realigns the board (restarts) before replaying, ignoring prior play", () => {
    const g = game();
    g.move("right");
    g.move("right"); // player has already pushed the box onto the goal
    expect(g.isWin()).toBe(true);
    expect(replaySolutionPrefix(g, moves, 1)).toBe(1);
    expect(g.player).toEqual({ x: 2, y: 1 }); // back on the solution line at step 1
    expect(g.boxAt(3, 1)).toBe(true);
    expect(g.isWin()).toBe(false); // restart undid the prior win, then replayed one move
    expect(g.moves + g.pushes).toBe(1); // counters reset by the restart, then one move
  });

  it("replays a pull move (P<DIR>) through game.pull", () => {
    // box (1,1) pinned on the left wall; goal at (2,1) where the player starts.
    const pullLevel = new Game(parseXsb(["#####", "#$+ #", "#####"].join("\n"))[0]);
    expect(replaySolutionPrefix(pullLevel, parseSolution("PR"), 1)).toBe(1);
    expect(pullLevel.boxAt(2, 1)).toBe(true); // pulled onto the goal
    expect(pullLevel.isWin()).toBe(true);
  });
});

describe("solution — boxMoveBoundaries", () => {
  it("lists the 1-based move count at each push/pull", () => {
    // walk, PUSH, walk, walk, PUSH, PULL → box-moves at moves #2, #5, #6.
    expect(boxMoveBoundaries(parseSolution("lUllRPR"))).toEqual([2, 5, 6]);
  });

  it("is empty when there are no box-moves", () => {
    expect(boxMoveBoundaries(parseSolution("llrr"))).toEqual([]);
  });
});

describe("solution — planHint (push-based, first push free)", () => {
  // 3 pushes among 5 moves: pushes end at moves 2, 4, 5 (the last is the winning push).
  const moves = parseSolution("lUlUU");

  it("reveals up to the first push for free", () => {
    expect(planHint(0, 1, moves)).toEqual({ moveCount: 2, boxMoves: 1, cost: 0, atEnd: false });
  });

  it("charges one token per push beyond the first", () => {
    // from 1 push to 2 pushes: one new push past the free first → cost 1.
    expect(planHint(1, 1, moves)).toEqual({ moveCount: 4, boxMoves: 2, cost: 1, atEnd: false });
  });

  it("never reveals the final winning push (caps at total - 1)", () => {
    // big hint from 0 wants +3 but caps at 2 of 3 pushes; pushes 2 of which 1 is free → cost 1.
    expect(planHint(0, 3, moves)).toEqual({ moveCount: 4, boxMoves: 2, cost: 1, atEnd: false });
    // already at the cap → nothing new.
    expect(planHint(2, 1, moves).atEnd).toBe(true);
  });

  it("offers a free walk-up on a single-push level, then nothing more", () => {
    const onePush = parseSolution("llU"); // walk, walk, PUSH (the winning move)
    expect(planHint(0, 1, onePush)).toEqual({ moveCount: 2, boxMoves: 0, cost: 0, atEnd: false });
    expect(planHint(0, 1, onePush)).not.toHaveProperty("atEnd", true); // first ask is the walk-up
  });
});
