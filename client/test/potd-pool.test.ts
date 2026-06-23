import { describe, expect, it } from "vitest";

import type { ManifestEntry } from "../src/engine/manifest";
import { buildDailyPool, handleDisplay, handleSuffix, parseSource } from "../src/potd/pool";
import { pickDailyIndex } from "../src/potd/select";

const entry = (n: number, source: string, extra: Partial<ManifestEntry> = {}): ManifestEntry => ({
  n,
  name: String(n),
  board: ["#@#"],
  solution: "u",
  par: 1,
  difficulty: 0.1,
  source,
  ...extra,
});

describe("parseSource", () => {
  it("splits '<corpus>:<n>'", () => {
    expect(parseSource("sasquatch7:33", 1)).toEqual({ corpus: "sasquatch7", n: 33 });
    expect(parseSource("microban:155", 1)).toEqual({ corpus: "microban", n: 155 });
  });

  it("falls back to ('curated', fallbackN) when missing or malformed", () => {
    expect(parseSource(undefined, 9)).toEqual({ corpus: "curated", n: 9 });
    expect(parseSource("garbage", 9)).toEqual({ corpus: "curated", n: 9 });
    expect(parseSource("microban:", 9)).toEqual({ corpus: "curated", n: 9 });
  });
});

describe("buildDailyPool", () => {
  const manifest: ManifestEntry[] = [
    entry(1, "microban:1"),
    entry(2, "autoban:1"), // excluded — generated set
    entry(3, "pullban:1"), // excluded — pull set
    entry(4, "pullban:5", { requires_pull: true }), // excluded — pull-required
    entry(5, "microban2:2"),
    entry(6, "sasquatch7:33"),
    entry(7, "xsokoban90:1"),
  ];

  it("drops autoban-/pullban-sourced and pull-required levels, preserving order", () => {
    expect(buildDailyPool(manifest).map((e) => e.source)).toEqual([
      "microban:1",
      "microban2:2",
      "sasquatch7:33",
      "xsokoban90:1",
    ]);
  });

  it("keeps every push-Sokoban source corpus", () => {
    const corpora = new Set(buildDailyPool(manifest).map((e) => parseSource(e.source, e.n).corpus));
    expect(corpora).toEqual(new Set(["microban", "microban2", "sasquatch7", "xsokoban90"]));
  });
});

describe("handleSuffix / handleDisplay", () => {
  it("is a stable 4-hex suffix for a given visitorId", () => {
    const a = handleSuffix("visitor-123");
    expect(a).toMatch(/^[0-9a-f]{4}$/);
    expect(handleSuffix("visitor-123")).toBe(a); // deterministic
    expect(handleDisplay("bob", "visitor-123")).toBe(`bob·${a}`);
  });

  it("distinguishes different visitors", () => {
    expect(handleSuffix("visitor-A")).not.toBe(handleSuffix("visitor-B"));
  });
});

describe("daily pick over the curated pool", () => {
  it("is deterministic per day and reaches multiple source corpora over a date range", () => {
    const manifest: ManifestEntry[] = [
      ...Array.from({ length: 50 }, (_, i) => entry(i + 1, `microban:${i + 1}`)),
      ...Array.from({ length: 50 }, (_, i) => entry(i + 51, `sasquatch1:${i + 1}`)),
      ...Array.from({ length: 50 }, (_, i) => entry(i + 101, `microban2:${i + 1}`)),
    ];
    const pool = buildDailyPool(manifest);
    const seen = new Set<string>();
    for (let month = 1; month <= 6; month++) {
      for (let day = 1; day <= 28; day++) {
        const dateStr = `2026-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        const idx = pickDailyIndex(dateStr, pool.length);
        expect(idx).toBeGreaterThanOrEqual(0);
        expect(idx).toBeLessThan(pool.length);
        expect(pickDailyIndex(dateStr, pool.length)).toBe(idx); // stable across calls
        const e = pool[idx];
        seen.add(parseSource(e.source, e.n).corpus);
      }
    }
    expect(seen.size).toBeGreaterThan(1);
  });
});
