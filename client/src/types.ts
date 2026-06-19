// Shared types for the Sokopelago client.

/** Integer grid coordinate. Origin top-left; +x right, +y down. */
export interface Vec {
  x: number;
  y: number;
}

/** Static (non-moving) layer of a board cell. */
export enum Tile {
  /** Outside the playfield (ragged padding) — never walkable, not drawn. */
  Void,
  Floor,
  Wall,
  /** A target square a box must end up on. */
  Goal,
}

/** A single parsed level: static layout plus dynamic start positions. */
export interface Level {
  /** 0-based parse order within the corpus. */
  index: number;
  /** Display name, e.g. "1" or "44 — Duh!". */
  name: string;
  width: number;
  height: number;
  /** Static layer, indexed [y][x] (row-major). */
  tiles: Tile[][];
  /** Player start position. */
  player: Vec;
  /** Box start positions. */
  boxes: Vec[];
}

export type Dir = "up" | "down" | "left" | "right";

/** Unit step for each direction. */
export const DELTA: Record<Dir, Vec> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};
