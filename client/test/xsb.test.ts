import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parseXsb } from "../src/xsb";
import { Tile } from "../src/types";

const corpus = readFileSync(
  new URL("../../levels/microban.xsb", import.meta.url),
  "utf8",
);

describe("parseXsb — Microban corpus", () => {
  const levels = parseXsb(corpus);

  it("parses the corpus to exactly 155 levels", () => {
    expect(levels).toHaveLength(155);
  });

  it("names levels by their title number (and subtitle when present)", () => {
    expect(levels[0].name).toBe("1");
    // Level 44 carries the subtitle 'Duh!' in the source file.
    expect(levels[43].name).toBe("44 — Duh!");
  });

  it("each level has exactly one player and matching boxes/goals", () => {
    for (const lvl of levels) {
      const goals = lvl.tiles.flat().filter((t) => t === Tile.Goal).length;
      expect(lvl.boxes.length).toBeGreaterThan(0);
      // A well-formed Sokoban level has one goal per box.
      expect(goals).toBe(lvl.boxes.length);
      // Player start sits inside the grid.
      expect(lvl.player.x).toBeGreaterThanOrEqual(0);
      expect(lvl.player.y).toBeGreaterThanOrEqual(0);
    }
  });
});

describe("parseXsb — format handling", () => {
  it("parses every glyph and splits static vs dynamic layers", () => {
    // 3x3: wall border, player on goal (+), box on goal (*), a goal (.).
    const xsb = ["#####", "#+$.#", "#  *#", "#####"].join("\n");
    const [lvl] = parseXsb(xsb);
    expect(lvl.width).toBe(5);
    expect(lvl.height).toBe(4);
    expect(lvl.player).toEqual({ x: 1, y: 1 });
    // boxes: $ at (2,1) and * at (3,2)
    expect(lvl.boxes).toEqual([
      { x: 2, y: 1 },
      { x: 3, y: 2 },
    ]);
    // goals: under player (+, 1,1), the '.' (3,1), and under * (3,2)
    expect(lvl.tiles[1][1]).toBe(Tile.Goal);
    expect(lvl.tiles[1][3]).toBe(Tile.Goal);
    expect(lvl.tiles[2][3]).toBe(Tile.Goal);
  });

  it("pads ragged rows with Void", () => {
    const xsb = ["####", "#@.#", "#$###", "####"].join("\n");
    const [lvl] = parseXsb(xsb);
    expect(lvl.width).toBe(5);
    // row 0 "####" is length 4; column 4 is padded Void.
    expect(lvl.tiles[0][4]).toBe(Tile.Void);
  });

  it("ignores header comment lines and bare ; titles", () => {
    const xsb = [
      "; a wordy header comment",
      "",
      "; 7",
      "",
      "###",
      "#@#",
      "#.#",
      "#$#",
      "###",
    ].join("\n");
    const levels = parseXsb(xsb);
    expect(levels).toHaveLength(1);
    expect(levels[0].name).toBe("7");
  });
});
