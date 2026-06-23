import { afterEach, describe, expect, it, vi } from "vitest";

import { pullControlVisible, loadSoloPullEnabled, saveSoloPullEnabled } from "../src/pull";

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

describe("pullControlVisible", () => {
  it("multiworld: shows only when the seed's pull_logic gates levels", () => {
    // The curated soundness fix: pull_logic off (e.g. curated) => no Pull item => hide the control.
    expect(pullControlVisible({ connected: true, pullLogic: false, soloPullEnabled: false })).toBe(
      false,
    );
    expect(pullControlVisible({ connected: true, pullLogic: true, soloPullEnabled: false })).toBe(
      true,
    );
  });

  it("multiworld ignores the solo opt-in", () => {
    // A leftover solo opt-in must not resurrect the free pull inside a non-pull_logic seed.
    expect(pullControlVisible({ connected: true, pullLogic: false, soloPullEnabled: true })).toBe(
      false,
    );
  });

  it("solo: follows the opt-in pref, regardless of pull_logic", () => {
    expect(pullControlVisible({ connected: false, pullLogic: false, soloPullEnabled: false })).toBe(
      false,
    );
    expect(pullControlVisible({ connected: false, pullLogic: false, soloPullEnabled: true })).toBe(
      true,
    );
    // pull_logic is a multiworld concept — it has no say in solo.
    expect(pullControlVisible({ connected: false, pullLogic: true, soloPullEnabled: false })).toBe(
      false,
    );
  });
});

describe("solo pull preference persistence", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults off and round-trips through localStorage", () => {
    vi.stubGlobal("localStorage", fakeStorage());
    expect(loadSoloPullEnabled()).toBe(false);
    saveSoloPullEnabled(true);
    expect(loadSoloPullEnabled()).toBe(true);
    saveSoloPullEnabled(false);
    expect(loadSoloPullEnabled()).toBe(false);
  });

  it("treats unavailable storage as opted out", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(loadSoloPullEnabled()).toBe(false);
    expect(() => saveSoloPullEnabled(true)).not.toThrow();
  });
});
