import { describe, expect, it } from "vitest";
import { Renderer } from "../src/engine/render";
import { parseXsb } from "../src/engine/xsb";
import { Game } from "../src/engine/board";

// A 5x3 board (walls border a player, a box, and a goal).
const game = new Game(parseXsb(["#####", "#@$.#", "#####"].join("\n"))[0]);

// Minimal 2D-context / canvas stand-ins — enough surface for draw() in the node test env.
function fakeCanvas() {
  const setTransform: number[][] = [];
  const ctx = {
    fillStyle: "",
    fillRect: () => {},
    beginPath: () => {},
    arc: () => {},
    fill: () => {},
    setTransform: (...a: number[]) => void setTransform.push(a),
  };
  const canvas = {
    width: 0,
    height: 0,
    style: {} as { width?: string; height?: string },
    getContext: () => ctx,
  };
  return { canvas, setTransform };
}

describe("Renderer.resize", () => {
  it("adopts a positive budget and fits cellSize to it", () => {
    const { canvas } = fakeCanvas();
    const r = new Renderer(canvas as unknown as HTMLCanvasElement);
    r.resize(500, 300);
    expect(r.maxWidth).toBe(500);
    expect(r.maxHeight).toBe(300);
    // cell = max(8, floor(min(500/5, 300/3))) = 100 -> 5*100 x 3*100.
    r.draw(game);
    expect(canvas.width).toBe(500);
    expect(canvas.height).toBe(300);
    expect(canvas.style.width).toBe("500px");
    expect(canvas.style.height).toBe("300px");
  });

  it("ignores non-positive values so the board never collapses", () => {
    const r = new Renderer(fakeCanvas().canvas as unknown as HTMLCanvasElement);
    r.resize(400, 400);
    r.resize(0, -10);
    expect(r.maxWidth).toBe(400);
    expect(r.maxHeight).toBe(400);
  });
});

describe("Renderer high-DPI", () => {
  it("backs the canvas at devicePixelRatio while keeping CSS size in layout px", () => {
    const orig = (globalThis as { devicePixelRatio?: number }).devicePixelRatio;
    (globalThis as { devicePixelRatio?: number }).devicePixelRatio = 2;
    try {
      const { canvas, setTransform } = fakeCanvas();
      const r = new Renderer(canvas as unknown as HTMLCanvasElement);
      r.resize(500, 300);
      r.draw(game);
      // Backing store doubled, CSS box unchanged, context scaled by dpr.
      expect(canvas.width).toBe(1000);
      expect(canvas.height).toBe(600);
      expect(canvas.style.width).toBe("500px");
      expect(canvas.style.height).toBe("300px");
      expect(setTransform[0]).toEqual([2, 0, 0, 2, 0, 0]);
    } finally {
      (globalThis as { devicePixelRatio?: number }).devicePixelRatio = orig;
    }
  });

  it("defaults to dpr=1 when devicePixelRatio is absent (node)", () => {
    const { canvas, setTransform } = fakeCanvas();
    const r = new Renderer(canvas as unknown as HTMLCanvasElement);
    r.resize(500, 300);
    r.draw(game);
    expect(canvas.width).toBe(500);
    expect(setTransform[0]).toEqual([1, 0, 0, 1, 0, 0]);
  });
});
