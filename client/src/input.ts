// Keyboard input: arrow keys / WASD to move, R to restart.

import type { Dir } from "./types";

export interface InputHandlers {
  onMove: (dir: Dir) => void;
  onRestart: () => void;
}

const KEY_TO_DIR: Record<string, Dir> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
  w: "up",
  s: "down",
  a: "left",
  d: "right",
  W: "up",
  S: "down",
  A: "left",
  D: "right",
};

/** Attach keyboard handlers to the window. Returns a detach function. */
export function attachInput(handlers: InputHandlers): () => void {
  const onKeyDown = (e: KeyboardEvent) => {
    // Held-key auto-repeat fires keydown repeatedly; we let it through so the
    // player keeps moving.
    const dir = KEY_TO_DIR[e.key];
    if (dir) {
      e.preventDefault();
      handlers.onMove(dir);
      return;
    }
    if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      handlers.onRestart();
    }
  };

  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}
