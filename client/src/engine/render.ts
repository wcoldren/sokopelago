// Canvas renderer. Kept behind this single module so a DOM/CSS-grid renderer
// could be swapped in without touching the game model or the play loop.

import { Tile } from "./types";
import type { Game } from "./board";

const COLORS = {
  bg: "#111114",
  wall: "#3b3b46",
  wallEdge: "#52525f",
  floor: "#23232b",
  goal: "#7a5c2e",
  box: "#c98a3c",
  boxOnGoal: "#6ee787",
  player: "#5aa9ff",
};

export class Renderer {
  private ctx: CanvasRenderingContext2D;
  /** Target maximum on-screen size; cell size is derived to fit the board. */
  maxWidth = 720;
  maxHeight = 540;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;
  }

  private cellSize(game: Game): number {
    const cell = Math.floor(
      Math.min(this.maxWidth / game.level.width, this.maxHeight / game.level.height),
    );
    return Math.max(8, cell);
  }

  draw(game: Game): void {
    const { level } = game;
    const cell = this.cellSize(game);
    this.canvas.width = level.width * cell;
    this.canvas.height = level.height * cell;

    const ctx = this.ctx;
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // Static layer.
    for (let y = 0; y < level.height; y++) {
      for (let x = 0; x < level.width; x++) {
        const t = level.tiles[y][x];
        if (t === Tile.Void) continue;
        const px = x * cell;
        const py = y * cell;
        if (t === Tile.Wall) {
          ctx.fillStyle = COLORS.wall;
          ctx.fillRect(px, py, cell, cell);
          ctx.fillStyle = COLORS.wallEdge;
          ctx.fillRect(px, py, cell, Math.max(2, cell * 0.12));
        } else {
          ctx.fillStyle = COLORS.floor;
          ctx.fillRect(px, py, cell, cell);
          if (t === Tile.Goal) {
            ctx.fillStyle = COLORS.goal;
            const r = cell * 0.16;
            ctx.beginPath();
            ctx.arc(px + cell / 2, py + cell / 2, r, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    }

    // Boxes.
    const pad = cell * 0.12;
    for (const b of game.boxes) {
      const onGoal = level.tiles[b.y][b.x] === Tile.Goal;
      ctx.fillStyle = onGoal ? COLORS.boxOnGoal : COLORS.box;
      ctx.fillRect(b.x * cell + pad, b.y * cell + pad, cell - 2 * pad, cell - 2 * pad);
    }

    // Player.
    ctx.fillStyle = COLORS.player;
    ctx.beginPath();
    ctx.arc(
      game.player.x * cell + cell / 2,
      game.player.y * cell + cell / 2,
      cell * 0.34,
      0,
      Math.PI * 2,
    );
    ctx.fill();
  }
}
