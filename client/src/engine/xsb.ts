// Parser for the XSB Sokoban level format.
//
// XSB board glyphs:
//   #  wall          (space)  floor / outside
//   @  player        +        player on goal
//   $  box           *        box on goal
//   .  goal
//
// A collection file interleaves boards with metadata:
//   - ";" comment lines; a bare "; <number>" line is a level title.
//   - "'name'" lines are an optional level subtitle (Skinner uses these).
//   - blank lines separate levels.
//
// A line is a board row iff it contains only board glyphs and at least one
// non-space glyph. Everything else is metadata or a separator.

import { Tile, type Level, type Vec } from "./types";

const BOARD_CHARS = /^[#@+$*. ]+$/;
const NON_SPACE_GLYPH = /[#@+$*.]/;
const TITLE_LINE = /^;\s*(\d+)\s*$/;
const SUBTITLE_LINE = /^'(.*)'$/;

function isBoardRow(line: string): boolean {
  return line.length > 0 && BOARD_CHARS.test(line) && NON_SPACE_GLYPH.test(line);
}

/** Parse XSB collection text into an ordered list of levels. */
export function parseXsb(text: string): Level[] {
  const levels: Level[] = [];
  let block: string[] = [];
  let pendingNum: number | null = null;
  let pendingSub: string | null = null;

  const flush = () => {
    if (block.length === 0) return;
    levels.push(buildLevel(block, levels.length, pendingNum, pendingSub));
    block = [];
    pendingNum = null;
    pendingSub = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.replace(/\r$/, "");
    if (isBoardRow(line)) {
      block.push(line);
      continue;
    }
    // Non-board line ends any board in progress, then may set the next label.
    flush();
    const trimmed = line.trim();
    const num = TITLE_LINE.exec(trimmed);
    if (num) {
      pendingNum = Number.parseInt(num[1], 10);
      continue;
    }
    const sub = SUBTITLE_LINE.exec(trimmed);
    if (sub) {
      pendingSub = sub[1];
    }
    // Other comments / blank lines are ignored.
  }
  flush();

  return levels;
}

function buildLevel(rows: string[], index: number, num: number | null, sub: string | null): Level {
  const label = num !== null ? String(num) : String(index + 1);
  const name = sub ? `${label} — ${sub}` : label;
  return levelFromBoard(rows, index, name);
}

/**
 * Build a level from its raw board rows with a caller-supplied name/index. Used both
 * by {@link parseXsb} and by the client when rendering boards bundled in the manifest
 * (`data/microban.json`), so a single geometry path serves both sources.
 */
export function levelFromBoard(rows: string[], index: number, name: string): Level {
  const height = rows.length;
  const width = Math.max(...rows.map((r) => r.length));

  const tiles: Tile[][] = [];
  let player: Vec | null = null;
  const boxes: Vec[] = [];

  for (let y = 0; y < height; y++) {
    const row: Tile[] = new Array<Tile>(width).fill(Tile.Void);
    const line = rows[y];
    for (let x = 0; x < line.length; x++) {
      switch (line[x]) {
        case "#":
          row[x] = Tile.Wall;
          break;
        case " ":
          row[x] = Tile.Floor;
          break;
        case ".":
          row[x] = Tile.Goal;
          break;
        case "$":
          row[x] = Tile.Floor;
          boxes.push({ x, y });
          break;
        case "*":
          row[x] = Tile.Goal;
          boxes.push({ x, y });
          break;
        case "@":
          row[x] = Tile.Floor;
          player = { x, y };
          break;
        case "+":
          row[x] = Tile.Goal;
          player = { x, y };
          break;
      }
    }
    tiles.push(row);
  }

  if (!player) {
    throw new Error(`Level ${name} has no player start (@ or +).`);
  }

  return { index, name, width, height, tiles, player, boxes };
}
