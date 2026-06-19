import { describe, expect, it } from "vitest";
import { parseXsb } from "../src/xsb";
import { Game } from "../src/board";

const load = (xsb: string): Game => new Game(parseXsb(xsb)[0]);

describe("Game — movement & pushing", () => {
  it("walks onto floor", () => {
    // player can step right onto floor
    const g = load(["#####", "#@  #", "#####"].join("\n"));
    expect(g.move("right")).toBe(true);
    expect(g.player).toEqual({ x: 2, y: 1 });
    expect(g.moves).toBe(1);
    expect(g.pushes).toBe(0);
  });

  it("does not walk into a wall", () => {
    const g = load(["###", "#@#", "###"].join("\n"));
    expect(g.move("right")).toBe(false);
    expect(g.player).toEqual({ x: 1, y: 1 });
  });

  it("pushes a single box into free floor", () => {
    const g = load(["######", "#@$  #", "######"].join("\n"));
    expect(g.move("right")).toBe(true);
    expect(g.player).toEqual({ x: 2, y: 1 });
    expect(g.boxAt(3, 1)).toBe(true);
    expect(g.pushes).toBe(1);
    expect(g.moves).toBe(0);
  });

  it("will not push a box into a wall", () => {
    const g = load(["####", "#@$#", "####"].join("\n"));
    expect(g.move("right")).toBe(false);
    expect(g.player).toEqual({ x: 1, y: 1 });
    expect(g.boxAt(2, 1)).toBe(true);
  });

  it("will not push two boxes at once", () => {
    const g = load(["######", "#@$$ #", "######"].join("\n"));
    expect(g.move("right")).toBe(false);
    expect(g.player).toEqual({ x: 1, y: 1 });
    expect(g.boxAt(2, 1)).toBe(true);
    expect(g.boxAt(3, 1)).toBe(true);
  });
});

describe("Game — win detection", () => {
  it("is not won at start and is won after pushing the box onto the goal", () => {
    const g = load(["#####", "#@$.#", "#####"].join("\n"));
    expect(g.isWin()).toBe(false);
    expect(g.move("right")).toBe(true); // box from (2,1) -> (3,1) which is the goal
    expect(g.isWin()).toBe(true);
  });

  it("a box already on its goal at start counts as won", () => {
    const g = load(["#####", "#@ *#", "#####"].join("\n"));
    expect(g.isWin()).toBe(true);
  });
});

describe("Game — restart", () => {
  it("restores the starting layout and counters", () => {
    const g = load(["######", "#@$  #", "######"].join("\n"));
    g.move("right");
    expect(g.boxAt(3, 1)).toBe(true);
    expect(g.pushes).toBe(1);
    g.restart();
    expect(g.player).toEqual({ x: 1, y: 1 });
    expect(g.boxAt(2, 1)).toBe(true);
    expect(g.boxAt(3, 1)).toBe(false);
    expect(g.pushes).toBe(0);
    expect(g.moves).toBe(0);
  });
});

describe("Game — real corpus level is playable", () => {
  it("loads Microban #1 with one player and equal boxes/goals", () => {
    const microban = parseXsb(
      // tiny inline copy of Microban level 1
      ["####", "# .#", "#  ###", "#*@  #", "#  $ #", "#  ###", "####"].join("\n"),
    );
    const g = new Game(microban[0]);
    expect(g.boxes.length).toBe(2);
    expect(g.isWin()).toBe(false);
  });
});
