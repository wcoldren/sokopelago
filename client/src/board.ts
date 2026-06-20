// Core Sokoban game model — pure logic, no DOM. Base rules only (Phase 0):
// walk onto floor/goal, push exactly one box, win when every box is on a goal.
// Abilities (pull, push-two, …) are out of scope until the expert tier.

import { DELTA, Tile, type Dir, type Level, type Vec } from "./types";

const key = (x: number, y: number): string => `${x},${y}`;

/** One reversible step, recorded before it is applied so `undo()` can replay it. */
interface MoveRecord {
  /** Player position before the move. */
  player: Vec;
  pushed: boolean;
  /** Box origin / destination (only when `pushed`). */
  boxFrom?: Vec;
  boxTo?: Vec;
}

export class Game {
  readonly level: Level;
  player: Vec;
  /** Live box positions (kept in sync with `boxKeys`). */
  boxes: Vec[];
  private boxKeys: Set<string>;
  private history: MoveRecord[] = [];
  moves = 0;
  pushes = 0;

  constructor(level: Level) {
    this.level = level;
    this.player = { ...level.player };
    this.boxes = level.boxes.map((b) => ({ ...b }));
    this.boxKeys = new Set(this.boxes.map((b) => key(b.x, b.y)));
  }

  /** Reset to the level's starting layout. */
  restart(): void {
    this.player = { ...this.level.player };
    this.boxes = this.level.boxes.map((b) => ({ ...b }));
    this.boxKeys = new Set(this.boxes.map((b) => key(b.x, b.y)));
    this.history = [];
    this.moves = 0;
    this.pushes = 0;
  }

  tileAt(x: number, y: number): Tile {
    if (y < 0 || y >= this.level.height || x < 0 || x >= this.level.width) {
      return Tile.Void;
    }
    return this.level.tiles[y][x];
  }

  private walkable(x: number, y: number): boolean {
    const t = this.tileAt(x, y);
    return t === Tile.Floor || t === Tile.Goal;
  }

  boxAt(x: number, y: number): boolean {
    return this.boxKeys.has(key(x, y));
  }

  /**
   * Attempt a move in `dir`. Pushes a single box if the cell beyond it is
   * free. Returns true iff the player (and possibly a box) actually moved.
   */
  move(dir: Dir): boolean {
    const d = DELTA[dir];
    const tx = this.player.x + d.x;
    const ty = this.player.y + d.y;

    if (!this.walkable(tx, ty)) return false;

    const record: MoveRecord = { player: { ...this.player }, pushed: false };

    if (this.boxAt(tx, ty)) {
      const bx = tx + d.x;
      const by = ty + d.y;
      // Can't push into a wall/void or into another box.
      if (!this.walkable(bx, by) || this.boxAt(bx, by)) return false;
      this.moveBox(tx, ty, bx, by);
      this.pushes++;
      record.pushed = true;
      record.boxFrom = { x: tx, y: ty };
      record.boxTo = { x: bx, y: by };
    } else {
      this.moves++;
    }

    this.player = { x: tx, y: ty };
    this.history.push(record);
    return true;
  }

  /** True if there is at least one move to undo. */
  canUndo(): boolean {
    return this.history.length > 0;
  }

  /** Reverse the most recent move (and its push, if any). Returns false if none. */
  undo(): boolean {
    const record = this.history.pop();
    if (!record) return false;
    if (record.pushed && record.boxFrom && record.boxTo) {
      this.moveBox(record.boxTo.x, record.boxTo.y, record.boxFrom.x, record.boxFrom.y);
      this.pushes--;
    } else {
      this.moves--;
    }
    this.player = { ...record.player };
    return true;
  }

  private moveBox(fromX: number, fromY: number, toX: number, toY: number): void {
    this.boxKeys.delete(key(fromX, fromY));
    this.boxKeys.add(key(toX, toY));
    const box = this.boxes.find((b) => b.x === fromX && b.y === fromY);
    if (box) {
      box.x = toX;
      box.y = toY;
    }
  }

  /** Solved when every box sits on a goal tile. */
  isWin(): boolean {
    return this.boxes.every((b) => this.tileAt(b.x, b.y) === Tile.Goal);
  }
}
