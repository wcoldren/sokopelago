import { afterEach, describe, expect, it, vi } from "vitest";

// The vitest env is "node" (no DOM), so stub a Map-backed localStorage to exercise persistence.
function fakeStorage(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, String(v)),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: (i) => Array.from(m.keys())[i] ?? null,
    get length() {
      return m.size;
    },
  };
}

describe("engine/stats visitorId", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it("mints once and persists across reloads (re-imports)", async () => {
    vi.stubGlobal("localStorage", fakeStorage());
    vi.resetModules();
    const { visitorId: first } = await import("../src/engine/stats");
    expect(first).toMatch(/.+/);
    expect(localStorage.getItem("sokopelago.visitor.v1")).toBe(first);

    // A fresh module evaluation (a new page load) reads the stored id back, not a new one.
    vi.resetModules();
    const { visitorId: second } = await import("../src/engine/stats");
    expect(second).toBe(first);
  });

  it("is distinct from the per-load sessionId", async () => {
    vi.stubGlobal("localStorage", fakeStorage());
    vi.resetModules();
    const { visitorId, sessionId } = await import("../src/engine/stats");
    expect(visitorId).not.toBe(sessionId);
  });
});
