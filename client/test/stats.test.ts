import { describe, expect, it } from "vitest";

import {
  STATS_SCHEMA,
  addVisit,
  derive,
  emptyStat,
  exportStore,
  importMerge,
  mergeStat,
  normalizeStat,
  type LevelStat,
  type StatsStore,
} from "../src/stats";

const ev = (moves: number, pushes: number, timeMs: number, ts = 0) => ({ moves, pushes, timeMs, ts });

describe("stats — derive", () => {
  it("rolls up visits, unique sessions, and per-metric bests", () => {
    const stat: LevelStat = {
      visits: 3,
      sessions: ["a", "a", "b"],
      solves: [ev(50, 14, 9000), ev(44, 12, 7000)],
    };
    const d = derive(stat);
    expect(d.visits).toBe(3);
    expect(d.uniqueVisits).toBe(2);
    expect(d.solveCount).toBe(2);
    expect(d.bestMoves).toBe(44);
    expect(d.bestPushes).toBe(12);
    expect(d.bestTimeMs).toBe(7000);
  });

  it("handles an absent record", () => {
    expect(derive(undefined).solveCount).toBe(0);
    expect(derive(undefined).bestMoves).toBeNull();
  });
});

describe("stats — record + merge helpers", () => {
  it("addVisit counts every open but dedups the session set", () => {
    const s = emptyStat();
    addVisit(s, "sess1");
    addVisit(s, "sess1");
    addVisit(s, "sess2");
    expect(s.visits).toBe(3);
    expect(derive(s).uniqueVisits).toBe(2);
  });

  it("mergeStat sums visits, unions sessions, concatenates solves", () => {
    const a: LevelStat = { visits: 1, sessions: ["x"], solves: [ev(40, 10, 3000)] };
    const b: LevelStat = { visits: 2, sessions: ["x", "y"], solves: [ev(38, 9, 2500)] };
    mergeStat(a, b);
    expect(a.visits).toBe(3);
    expect(new Set(a.sessions)).toEqual(new Set(["x", "y"]));
    expect(a.solves).toHaveLength(2);
    expect(derive(a).bestMoves).toBe(38);
  });
});

describe("stats — export/import round-trip", () => {
  it("exports a schema-tagged object and merges back on import", () => {
    const store: StatsStore = {
      microban: { 7: { visits: 2, sessions: ["s"], solves: [ev(40, 12, 5000)] } },
    };
    const exported = exportStore(store, "Player1", 123);
    expect(exported.schema).toBe(STATS_SCHEMA);
    expect(exported.player).toBe("Player1");

    const dest: StatsStore = {};
    expect(importMerge(dest, exported)).toBe(true);
    expect(derive(dest.microban[7]).bestMoves).toBe(40);

    // Importing the same export again merges (visits sum, event log grows).
    importMerge(dest, exported);
    expect(dest.microban[7].visits).toBe(4);
    expect(dest.microban[7].solves).toHaveLength(2);
  });

  it("rejects a payload that isn't a Sokopelago stats file", () => {
    expect(importMerge({}, { schema: "nope", corpora: {} })).toBe(false);
    expect(importMerge({}, null)).toBe(false);
  });

  it("normalizeStat coerces malformed input to a safe record", () => {
    const n = normalizeStat({ visits: "x", solves: [{ moves: "abc" }], sessions: [1, "ok"] });
    expect(n.visits).toBe(0);
    expect(n.sessions).toEqual(["ok"]);
    expect(n.solves[0].moves).toBe(0);
  });
});
