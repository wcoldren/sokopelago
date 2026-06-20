import { describe, expect, it } from "vitest";

import { nextMove, parseSolution } from "../src/solution";

describe("solution — parseSolution", () => {
  it("maps LURD characters to directions, case-insensitively", () => {
    expect(parseSolution("uDlR")).toEqual(["up", "down", "left", "right"]);
  });

  it("ignores characters that are not move letters", () => {
    expect(parseSolution("u x d!")).toEqual(["up", "down"]);
  });

  it("returns an empty list for an empty string", () => {
    expect(parseSolution("")).toEqual([]);
  });
});

describe("solution — nextMove", () => {
  it("returns the move at the index", () => {
    const moves = parseSolution("urd");
    expect(nextMove(moves, 0)).toBe("up");
    expect(nextMove(moves, 2)).toBe("down");
  });

  it("returns null out of range", () => {
    const moves = parseSolution("ur");
    expect(nextMove(moves, -1)).toBeNull();
    expect(nextMove(moves, 2)).toBeNull();
  });
});
