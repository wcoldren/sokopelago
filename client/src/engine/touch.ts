// Touch input: swipe on the board to move. Translates pointer gestures into the same
// InputHandlers calls as the keyboard (see input.ts), so the engine, solver, and play loop never
// learn that touch exists — touch is purely a second translator.

import type { Dir } from "./types";
import type { InputHandlers } from "./input";

/** Minimum pointer travel (CSS px) before a drag counts as a swipe rather than a tap. */
const SWIPE_THRESHOLD = 24;

/**
 * Classify a pointer delta into a swipe direction, or null when the travel is below threshold
 * (i.e. a tap — emit nothing). The dominant axis wins; a perfect diagonal resolves to horizontal.
 *
 * Pure: no DOM, so it's exercised directly in the node test env (like board.ts / pull.ts).
 */
export function classifySwipe(dx: number, dy: number, threshold = SWIPE_THRESHOLD): Dir | null {
  const absX = Math.abs(dx);
  const absY = Math.abs(dy);
  if (Math.max(absX, absY) < threshold) return null;
  if (absX >= absY) return dx < 0 ? "left" : "right";
  return dy < 0 ? "up" : "down";
}

/**
 * Attach swipe-to-move on `target` (the board element). Returns a detach function.
 *
 * Movement only: a swipe emits `onMove(dir)`. The sticky "pull mode" (where plain moves pull) is
 * owned by the caller's `onMove`, exactly as for the keyboard — so touch needs no separate pull
 * gesture; arming pull via the Pull button and then swiping just works. Listeners are scoped to
 * `target`, never `window`, so the connect panel and page chrome aren't hijacked. Pair this with
 * `touch-action: none` on `target` so the browser doesn't scroll/pan the gesture away.
 */
export function attachTouchInput(target: HTMLElement, handlers: InputHandlers): () => void {
  let startX = 0;
  let startY = 0;
  let pointerId: number | null = null;

  const onPointerDown = (e: PointerEvent) => {
    if (pointerId !== null) return; // ignore secondary pointers mid-gesture
    pointerId = e.pointerId;
    startX = e.clientX;
    startY = e.clientY;
    // Keep receiving the gesture even if the finger drifts off the board before lifting.
    target.setPointerCapture?.(e.pointerId);
  };

  const onPointerUp = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
    const dir = classifySwipe(e.clientX - startX, e.clientY - startY);
    if (!dir) return; // a tap — emit nothing
    e.preventDefault();
    handlers.onMove(dir);
  };

  const onPointerCancel = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
  };

  target.addEventListener("pointerdown", onPointerDown);
  target.addEventListener("pointerup", onPointerUp);
  target.addEventListener("pointercancel", onPointerCancel);
  return () => {
    target.removeEventListener("pointerdown", onPointerDown);
    target.removeEventListener("pointerup", onPointerUp);
    target.removeEventListener("pointercancel", onPointerCancel);
  };
}
