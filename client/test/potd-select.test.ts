import { describe, expect, it } from "vitest";

import { utcDayString, pickDailyIndex, todaysIndex } from "../src/potd/select";

describe("utcDayString", () => {
  it("formats the UTC calendar day as YYYY-MM-DD", () => {
    expect(utcDayString(new Date("2026-06-21T12:00:00Z"))).toBe("2026-06-21");
    expect(utcDayString(new Date("2026-01-05T00:00:00Z"))).toBe("2026-01-05");
  });

  it("is timezone-independent: the same instant yields the same day everywhere", () => {
    // The same absolute instant, built two ways (ISO-Z and epoch ms). A local-time-based
    // formatter would diverge by locale; the UTC one cannot.
    const instant = Date.parse("2026-06-21T23:30:00Z");
    expect(utcDayString(new Date(instant))).toBe(utcDayString(new Date("2026-06-21T23:30:00Z")));
    expect(utcDayString(new Date(instant))).toBe("2026-06-21");
  });

  it("rolls over exactly at 00:00 UTC", () => {
    expect(utcDayString(new Date("2026-06-21T23:59:59.999Z"))).toBe("2026-06-21");
    expect(utcDayString(new Date("2026-06-22T00:00:00.000Z"))).toBe("2026-06-22");
  });
});

describe("pickDailyIndex", () => {
  it("is deterministic for a given day string", () => {
    expect(pickDailyIndex("2026-06-21", 155)).toBe(pickDailyIndex("2026-06-21", 155));
  });

  it("stays within [0, poolSize)", () => {
    for (const day of ["2026-01-01", "2026-06-21", "2026-12-31", "2030-02-28"]) {
      const i = pickDailyIndex(day, 155);
      expect(i).toBeGreaterThanOrEqual(0);
      expect(i).toBeLessThan(155);
    }
  });

  it("does NOT march up the list like dayIndex % len", () => {
    // Consecutive days must not produce a +1 ramp (the failure mode the kickoff calls out).
    const days = Array.from({ length: 10 }, (_, k) => `2026-06-${String(k + 1).padStart(2, "0")}`);
    const idx = days.map((d) => pickDailyIndex(d, 155));
    const isRamp = idx.every((v, k) => k === 0 || v === idx[k - 1] + 1);
    expect(isRamp).toBe(false);
    // And it actually varies day to day (not a constant).
    expect(new Set(idx).size).toBeGreaterThan(1);
  });

  it("no repeat until the pool is exhausted: any poolSize-day window is a full permutation", () => {
    // Walk poolSize consecutive UTC days; a fixed permutation indexed by day-number means each
    // window of poolSize days shows every index exactly once (no early repeat).
    const pool = 7;
    const start = Date.parse("2026-03-01T00:00:00Z");
    const window = Array.from({ length: pool }, (_, k) =>
      pickDailyIndex(utcDayString(new Date(start + k * 86_400_000)), pool),
    );
    expect(new Set(window).size).toBe(pool); // all distinct
    expect([...window].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4, 5, 6]); // covers 0..pool-1
  });

  it("stays distinct across a cycle boundary (unaligned window)", () => {
    // Start at an arbitrary offset so the window straddles the wrap point; still a full permutation.
    const pool = 7;
    const start = Date.parse("2026-03-04T00:00:00Z");
    const window = Array.from({ length: pool }, (_, k) =>
      pickDailyIndex(utcDayString(new Date(start + k * 86_400_000)), pool),
    );
    expect(new Set(window).size).toBe(pool);
  });

  it("guards an empty pool", () => {
    expect(pickDailyIndex("2026-06-21", 0)).toBe(0);
  });
});

describe("todaysIndex", () => {
  it("equals pickDailyIndex of the instant's UTC day", () => {
    const now = new Date("2026-06-21T08:15:00Z");
    expect(todaysIndex(155, now)).toBe(pickDailyIndex("2026-06-21", 155));
  });
});
