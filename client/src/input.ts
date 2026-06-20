// Keyboard input: arrow keys / WASD to move, R restart, U undo, H hint, K skip.

import type { Dir } from "./types";

export interface InputHandlers {
  onMove: (dir: Dir) => void;
  onRestart: () => void;
  onUndo?: () => void;
  onHint?: () => void;
  onSkip?: () => void;
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
    // Don't hijack typing: while a form field (connect panel, etc.) is focused,
    // let WASD/arrows/R reach the input instead of driving the board.
    const target = e.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable)
    ) {
      return;
    }

    // Held-key auto-repeat fires keydown repeatedly; we let it through so the
    // player keeps moving.
    const dir = KEY_TO_DIR[e.key];
    if (dir) {
      e.preventDefault();
      handlers.onMove(dir);
      return;
    }
    const action: Record<string, (() => void) | undefined> = {
      r: handlers.onRestart,
      u: handlers.onUndo,
      h: handlers.onHint,
      k: handlers.onSkip,
    };
    const handler = action[e.key.toLowerCase()];
    if (handler) {
      e.preventDefault();
      handler();
    }
  };

  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}
