import { describe, expect, it, vi } from "vitest";
import { classifySwipe, attachTouchInput } from "../src/engine/touch";
import type { InputHandlers } from "../src/engine/input";

describe("classifySwipe", () => {
  it("classifies the dominant axis once past threshold", () => {
    expect(classifySwipe(40, 0)).toBe("right");
    expect(classifySwipe(-40, 0)).toBe("left");
    expect(classifySwipe(0, 40)).toBe("down");
    expect(classifySwipe(0, -40)).toBe("up");
  });

  it("uses the larger axis when the gesture is diagonal", () => {
    expect(classifySwipe(50, 20)).toBe("right");
    expect(classifySwipe(20, -50)).toBe("up");
  });

  it("returns null for a tap (travel below threshold)", () => {
    expect(classifySwipe(0, 0)).toBeNull();
    expect(classifySwipe(10, 10)).toBeNull();
    expect(classifySwipe(-23, 5)).toBeNull();
  });

  it("honors a custom threshold", () => {
    expect(classifySwipe(10, 0, 8)).toBe("right");
    expect(classifySwipe(10, 0, 24)).toBeNull();
  });
});

// A minimal stand-in for the board element: records listeners so the test can dispatch synthetic
// pointer events (the client tests run in node, with no DOM / real PointerEvent).
function fakeTarget() {
  const map = new Map<string, Set<(e: unknown) => void>>();
  return {
    setPointerCapture: vi.fn(),
    addEventListener(type: string, fn: (e: unknown) => void) {
      (map.get(type) ?? map.set(type, new Set()).get(type)!).add(fn);
    },
    removeEventListener(type: string, fn: (e: unknown) => void) {
      map.get(type)?.delete(fn);
    },
    dispatch(type: string, e: unknown) {
      for (const fn of [...(map.get(type) ?? [])]) fn(e);
    },
    count(type: string) {
      return map.get(type)?.size ?? 0;
    },
  };
}

type Target = ReturnType<typeof fakeTarget>;

function newHandlers() {
  return { onMove: vi.fn(), onRestart: vi.fn() } satisfies InputHandlers;
}

function swipe(t: Target, x0: number, y0: number, x1: number, y1: number, id = 1) {
  t.dispatch("pointerdown", { pointerId: id, clientX: x0, clientY: y0 });
  t.dispatch("pointerup", { pointerId: id, clientX: x1, clientY: y1, preventDefault: vi.fn() });
}

describe("attachTouchInput", () => {
  it("emits onMove with the swiped direction", () => {
    const t = fakeTarget();
    const h = newHandlers();
    attachTouchInput(t as unknown as HTMLElement, h);

    swipe(t, 100, 100, 160, 100);
    expect(h.onMove).toHaveBeenLastCalledWith("right");
    swipe(t, 100, 100, 40, 100);
    expect(h.onMove).toHaveBeenLastCalledWith("left");
    swipe(t, 100, 100, 100, 160);
    expect(h.onMove).toHaveBeenLastCalledWith("down");
    swipe(t, 100, 100, 100, 40);
    expect(h.onMove).toHaveBeenLastCalledWith("up");
    expect(h.onMove).toHaveBeenCalledTimes(4);
  });

  it("emits nothing for a tap (no meaningful travel)", () => {
    const t = fakeTarget();
    const h = newHandlers();
    attachTouchInput(t as unknown as HTMLElement, h);
    swipe(t, 100, 100, 104, 103);
    expect(h.onMove).not.toHaveBeenCalled();
  });

  it("ignores a stray pointerup from a pointer it isn't tracking", () => {
    const t = fakeTarget();
    const h = newHandlers();
    attachTouchInput(t as unknown as HTMLElement, h);
    t.dispatch("pointerdown", { pointerId: 1, clientX: 0, clientY: 0 });
    t.dispatch("pointerup", {
      pointerId: 2, // different pointer
      clientX: 100,
      clientY: 0,
      preventDefault: vi.fn(),
    });
    expect(h.onMove).not.toHaveBeenCalled();
  });

  it("detach removes every listener", () => {
    const t = fakeTarget();
    const detach = attachTouchInput(t as unknown as HTMLElement, newHandlers());
    expect(t.count("pointerdown")).toBe(1);
    expect(t.count("pointerup")).toBe(1);
    expect(t.count("pointercancel")).toBe(1);
    detach();
    expect(t.count("pointerdown")).toBe(0);
    expect(t.count("pointerup")).toBe(0);
    expect(t.count("pointercancel")).toBe(0);
  });
});
