import { describe, expect, it } from "vitest";

import { nextMove, parseSolution, replaySolutionPrefix } from "../src/solution";
import { parseXsb } from "../src/xsb";
import { Game } from "../src/board";

// A one-line level: player, a gap, a box, then its goal. Solution "rr" = walk right,
// then push the box onto the goal.
const SOLVABLE = ["######", "#@ $.#", "######"].join("\n");
const game = (): Game => new Game(parseXsb(SOLVABLE)[0]);

describe("solution — parseSolution", () => {
  it("maps LURD characters to (walk/push) directions, case-insensitively", () => {
    expect(parseSolution("uDlR")).toEqual([
      { dir: "up", pull: false },
      { dir: "down", pull: false },
      { dir: "left", pull: false },
      { dir: "right", pull: false },
    ]);
  });

  it("parses a P<DIR> unit as a pull move", () => {
    expect(parseSolution("rPRd")).toEqual([
      { dir: "right", pull: false },
      { dir: "right", pull: true },
      { dir: "down", pull: false },
    ]);
  });

  it("ignores characters that are not move letters", () => {
    expect(parseSolution("u x d!")).toEqual([
      { dir: "up", pull: false },
      { dir: "down", pull: false },
    ]);
  });

  it("returns an empty list for an empty string", () => {
    expect(parseSolution("")).toEqual([]);
  });
});

describe("solution — nextMove", () => {
  it("returns the move at the index", () => {
    const moves = parseSolution("urd");
    expect(nextMove(moves, 0)).toEqual({ dir: "up", pull: false });
    expect(nextMove(moves, 2)).toEqual({ dir: "down", pull: false });
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
