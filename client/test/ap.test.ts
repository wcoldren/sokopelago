import { describe, expect, it } from "vitest";

import {
  EFF_LOC_BASE,
  FILLER_ID,
  HINT_ID,
  KEY_BASE,
  LOC_BASE,
  PAR_LOC_BASE,
  PULL_ID,
  SKIP_ID,
  TRAP_ID_BASE,
  UNDO_ID,
  escapeValveForItem,
  isPullItem,
  levelForEfficientLocationId,
  levelForLocationId,
  levelForParLocationId,
  locationIdForEfficientLevel,
  locationIdForLevel,
  locationIdForParLevel,
  worldForKeyItem,
} from "../src/ap/ids";
import {
  chainFloor,
  difficultyForLevel,
  efficientThresholdForLevel,
  isGoalMet,
  levelsInWorld,
  parForLevel,
  requiresPull,
  solvedInSeed,
  worldOfLevel,
  type SlotData,
} from "../src/ap/slotData";
import { resolveServerUrl, Session, type SessionCallbacks } from "../src/ap/session";
import { derive } from "../src/stats";

describe("ap/session — resolveServerUrl", () => {
  it("honors an explicit scheme", () => {
    expect(resolveServerUrl("wss://archipelago.gg:38281")).toBe("wss://archipelago.gg:38281");
    expect(resolveServerUrl("ws://localhost:38281")).toBe("ws://localhost:38281");
  });

  it("defaults local/self-hosted hosts to ws://", () => {
    expect(resolveServerUrl("localhost:38281")).toBe("ws://localhost:38281");
    expect(resolveServerUrl("127.0.0.1:38281")).toBe("ws://127.0.0.1:38281");
    expect(resolveServerUrl("192.168.1.5:38281")).toBe("ws://192.168.1.5:38281");
  });

  it("leaves remote hosts bare (library tries wss then ws)", () => {
    expect(resolveServerUrl("archipelago.gg:38281")).toBe("archipelago.gg:38281");
  });
});

describe("ap/ids — network id arithmetic", () => {
  it("round-trips location id <-> level number", () => {
    for (const n of [1, 2, 30, 155]) {
      expect(locationIdForLevel(n)).toBe(LOC_BASE + n);
      expect(levelForLocationId(locationIdForLevel(n))).toBe(n);
    }
  });

  it("rejects out-of-range / foreign location ids", () => {
    expect(levelForLocationId(LOC_BASE)).toBeNull(); // n = 0
    expect(levelForLocationId(LOC_BASE + 156)).toBeNull();
    expect(levelForLocationId(KEY_BASE + 2)).toBeNull(); // an item id, not a location
  });

  it("round-trips par-location id <-> level number, in a band of its own", () => {
    for (const n of [1, 2, 30, 155]) {
      expect(locationIdForParLevel(n)).toBe(PAR_LOC_BASE + n);
      expect(levelForParLocationId(locationIdForParLevel(n))).toBe(n);
    }
    // The two bands don't overlap: a solve id is not a par id and vice-versa.
    expect(levelForParLocationId(locationIdForLevel(30))).toBeNull();
    expect(levelForLocationId(locationIdForParLevel(30))).toBeNull();
    expect(levelForParLocationId(PAR_LOC_BASE)).toBeNull(); // n = 0
    expect(levelForParLocationId(PAR_LOC_BASE + 156)).toBeNull();
  });

  it("maps world-key item ids to world index", () => {
    for (const i of [2, 3, 155]) {
      expect(worldForKeyItem(KEY_BASE + i)).toBe(i);
    }
  });

  it("treats filler and the keyless World 1 slot as non-keys", () => {
    expect(worldForKeyItem(FILLER_ID)).toBeNull(); // KEY_BASE + 1
    expect(worldForKeyItem(KEY_BASE + 1)).toBeNull();
    expect(worldForKeyItem(KEY_BASE + 156)).toBeNull();
  });
});

describe("ap/ids — escapeValveForItem", () => {
  it("classifies skip / undo / hint", () => {
    expect(escapeValveForItem(SKIP_ID)).toEqual({ kind: "skip" });
    expect(escapeValveForItem(UNDO_ID)).toEqual({ kind: "undo" });
    expect(escapeValveForItem(HINT_ID)).toEqual({ kind: "hint" });
  });

  it("classifies the three trap variants by offset", () => {
    expect(escapeValveForItem(TRAP_ID_BASE)).toEqual({ kind: "trap", trap: "scramble" });
    expect(escapeValveForItem(TRAP_ID_BASE + 1)).toEqual({ kind: "trap", trap: "decoy" });
    expect(escapeValveForItem(TRAP_ID_BASE + 2)).toEqual({ kind: "trap", trap: "reversed" });
  });

  it("returns null for keys, filler, and locations", () => {
    expect(escapeValveForItem(KEY_BASE + 2)).toBeNull();
    expect(escapeValveForItem(FILLER_ID)).toBeNull();
    expect(escapeValveForItem(LOC_BASE + 1)).toBeNull();
    expect(escapeValveForItem(TRAP_ID_BASE + 3)).toBeNull();
    expect(escapeValveForItem(PULL_ID)).toBeNull(); // the ability is not an escape valve
  });
});

describe("ap/ids — isPullItem", () => {
  it("recognizes only the Pull ability id", () => {
    expect(isPullItem(PULL_ID)).toBe(true);
    expect(isPullItem(SKIP_ID)).toBe(false);
    expect(isPullItem(KEY_BASE + 2)).toBe(false);
  });
});

// A 25-level seed in 3 worlds (10/10/5), matching chunk_levels(25, 10).
function sampleSlot(overrides: Partial<SlotData> = {}): SlotData {
  const region_map: Record<string, number[]> = {
    "1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "2": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    "3": [21, 22, 23, 24, 25],
  };
  return {
    corpus: "microban",
    level_count: 25,
    levels_per_region: 10,
    levels: Array.from({ length: 25 }, (_, i) => i + 1),
    region_map,
    goal: "beat_final_region",
    goal_solve_count: 15,
    goal_boss_level: 25,
    final_world: 3,
    seed_name: "TEST",
    player_name: "Tester",
    player_id: 1,
    ...overrides,
  };
}

describe("ap/slotData — region derivations", () => {
  it("maps each level to its world", () => {
    const w = worldOfLevel(sampleSlot());
    expect(w.get(1)).toBe(1);
    expect(w.get(10)).toBe(1);
    expect(w.get(11)).toBe(2);
    expect(w.get(21)).toBe(3);
    expect(w.get(25)).toBe(3);
    expect(w.size).toBe(25);
  });

  it("lists levels in a world (empty for unknown worlds)", () => {
    expect(levelsInWorld(sampleSlot(), 3)).toEqual([21, 22, 23, 24, 25]);
    expect(levelsInWorld(sampleSlot(), 99)).toEqual([]);
  });

  it("counts solved levels within the seed", () => {
    const solved = new Set([1, 2, 25, 999]); // 999 is not in the seed
    expect(solvedInSeed(sampleSlot(), solved)).toBe(3);
  });
});

describe("ap/slotData — isGoalMet", () => {
  it("beat_final_region: needs every level in the final world", () => {
    const slot = sampleSlot();
    const partial = new Set([21, 22, 23, 24]); // missing 25
    const full = new Set([21, 22, 23, 24, 25]);
    expect(isGoalMet(slot, partial)).toBe(false);
    expect(isGoalMet(slot, full)).toBe(true);
  });

  it("solve_count: needs goal_solve_count seed levels solved", () => {
    const slot = sampleSlot({ goal: "solve_count", goal_solve_count: 3 });
    expect(isGoalMet(slot, new Set([1, 2]))).toBe(false);
    expect(isGoalMet(slot, new Set([1, 2, 3]))).toBe(true);
    expect(isGoalMet(slot, new Set([1, 2, 3, 4]))).toBe(true);
  });

  it("boss_level: needs the boss level solved", () => {
    const slot = sampleSlot({ goal: "boss_level", goal_boss_level: 17 });
    expect(isGoalMet(slot, new Set([16, 18]))).toBe(false);
    expect(isGoalMet(slot, new Set([17]))).toBe(true);
  });
});

describe("ap/slotData — parForLevel", () => {
  it("returns the push-par when present", () => {
    const slot = sampleSlot({ par: { "7": 10, "8": 0 } });
    expect(parForLevel(slot, 7)).toBe(10);
  });

  it("returns null for missing, zero, or absent par data", () => {
    expect(parForLevel(sampleSlot({ par: { "8": 0 } }), 8)).toBeNull(); // non-positive
    expect(parForLevel(sampleSlot({ par: { "7": 10 } }), 9)).toBeNull(); // not in map
    expect(parForLevel(sampleSlot(), 7)).toBeNull(); // no par map at all
  });
});

describe("ap/slotData — difficultyForLevel", () => {
  it("returns the normalized difficulty when present", () => {
    expect(difficultyForLevel(sampleSlot({ difficulty: { "7": 0.42 } }), 7)).toBe(0.42);
  });

  it("treats 0 as a valid (easiest) difficulty, not missing", () => {
    expect(difficultyForLevel(sampleSlot({ difficulty: { "7": 0 } }), 7)).toBe(0);
  });

  it("returns null when the level is absent or no difficulty map shipped", () => {
    expect(difficultyForLevel(sampleSlot({ difficulty: { "7": 0.42 } }), 9)).toBeNull();
    expect(difficultyForLevel(sampleSlot(), 7)).toBeNull();
  });
});

describe("ap/slotData — requiresPull", () => {
  it("is true only for levels flagged in requires_pull", () => {
    const slot = sampleSlot({ pull_logic: true, requires_pull: { "21": true } });
    expect(requiresPull(slot, 21)).toBe(true);
    expect(requiresPull(slot, 22)).toBe(false);
    expect(requiresPull(sampleSlot(), 21)).toBe(false); // no map at all
  });
});

describe("ap/slotData — chainFloor", () => {
  it("returns the shipped per-world floor", () => {
    const slot = sampleSlot({ chain_floors: { "1": 0, "2": 0, "3": 2 } });
    expect(chainFloor(slot, 1)).toBe(0);
    expect(chainFloor(slot, 3)).toBe(2);
  });

  it("defaults to 0 when absent, missing, or negative (back-compat / flat unlock)", () => {
    expect(chainFloor(sampleSlot(), 2)).toBe(0); // no chain_floors map at all (pre-0.7)
    expect(chainFloor(sampleSlot({ chain_floors: { "2": 1 } }), 9)).toBe(0); // world not in map
    expect(chainFloor(sampleSlot({ chain_floors: { "2": -1 } }), 2)).toBe(0); // guard negatives
  });
});

// A 6-world seed exercising the 0.7 count-floor chain + the all-keys boss gate.
function chainSlot(overrides: Partial<SlotData> = {}): SlotData {
  return sampleSlot({
    level_count: 12,
    levels_per_region: 2,
    levels: Array.from({ length: 12 }, (_, i) => i + 1),
    region_map: {
      "1": [1, 2],
      "2": [3, 4],
      "3": [5, 6],
      "4": [7, 8],
      "5": [9, 10],
      "6": [11, 12],
    },
    final_world: 6,
    chain_floors: { "1": 0, "2": 0, "3": 0, "4": 1, "5": 2, "6": 5 },
    boss_all_keys: true,
    ...overrides,
  });
}

describe("ap/session — chained unlocks (0.7 accurate logic)", () => {
  it("unlocks a body world only when its own key AND the count-floor are met", () => {
    const { s, client } = mockSession();
    const slot = chainSlot();
    peek(s).slot = slot;
    peek(s).worldOf = worldOfLevel(slot);
    // World 5 has floor 2: its own key alone (1 key total) is not enough.
    client.items.received = [{ id: KEY_BASE + 5 }];
    peek(s).syncItems(true);
    expect(s.unlockedWorlds.has(5)).toBe(false);
    expect(s.isLevelUnlocked(9)).toBe(false); // a level in world 5
    // A second key reaches the floor (2 keys total) -> world 5 unlocks.
    client.items.received = [{ id: KEY_BASE + 5 }, { id: KEY_BASE + 2 }];
    peek(s).syncItems(false);
    expect(s.unlockedWorlds.has(5)).toBe(true);
    expect(s.isLevelUnlocked(9)).toBe(true);
  });

  it("does not unlock a world whose own key is missing even with enough total keys", () => {
    const { s, client } = mockSession();
    peek(s).slot = chainSlot();
    // Three keys held (floor 2 for world 5 satisfied) but NOT world 5's own key.
    client.items.received = [{ id: KEY_BASE + 2 }, { id: KEY_BASE + 3 }, { id: KEY_BASE + 4 }];
    peek(s).syncItems(true);
    expect(s.unlockedWorlds.has(5)).toBe(false);
  });

  it("unlocks the boss world only once every key is held", () => {
    const { s, client } = mockSession();
    const slot = chainSlot();
    peek(s).slot = slot;
    peek(s).worldOf = worldOfLevel(slot);
    client.items.received = [2, 3, 4, 5].map((w) => ({ id: KEY_BASE + w })); // all but key 6
    peek(s).syncItems(true);
    expect(s.unlockedWorlds.has(6)).toBe(false);
    expect(s.isLevelUnlocked(11)).toBe(false); // a level in the boss world
    client.items.received = [2, 3, 4, 5, 6].map((w) => ({ id: KEY_BASE + w }));
    peek(s).syncItems(false);
    expect(s.unlockedWorlds.has(6)).toBe(true);
    expect(s.isLevelUnlocked(11)).toBe(true);
  });

  it("back-compat: with no chain_floors / boss_all_keys, a world unlocks on its own key", () => {
    const { s, client } = mockSession();
    // sampleSlot has no chain_floors and no boss_all_keys (pre-0.7 / flat).
    peek(s).slot = sampleSlot();
    client.items.received = [{ id: KEY_BASE + 3 }]; // world 3 is the final world here
    peek(s).syncItems(true);
    expect(s.unlockedWorlds.has(3)).toBe(true); // unset boss flag -> normal single-key unlock
  });
});

// The session is a thin wrapper over archipelago.js; we inject a stub client to
// exercise inventory tallying, the skip->check routing invariant, and trap firing.
interface SessionInternals {
  client: unknown;
  slot: SlotData | null;
  worldOf: Map<number, number>;
  received: { skip: number; undo: number; hint: number };
  syncItems(suppressTraps: boolean): void;
}
const peek = (s: Session): SessionInternals => s as unknown as SessionInternals;

function mockSession(onTrap: (v: string) => void = () => {}) {
  const checked: number[] = [];
  const callbacks: SessionCallbacks = {
    onConnected: () => {},
    onUpdate: () => {},
    onGoal: () => {},
    onMessage: () => {},
    onTrap: (variant) => onTrap(variant),
    onDisconnect: () => {},
  };
  const s = new Session(callbacks);
  const client = {
    authenticated: true,
    check: (id: number) => checked.push(id),
    goal: () => {},
    items: { received: [] as Array<{ id: number }> },
    storage: { prepare: () => ({ add: () => ({ commit: () => undefined }) }) },
  };
  peek(s).client = client;
  return { s, client, checked };
}

describe("ap/session — escape valves", () => {
  it("tallies received valve items and unlocks worlds from the backlog", () => {
    const { s, client } = mockSession();
    peek(s).slot = sampleSlot(); // unlocks are recomputed against the seed's worlds
    client.items.received = [
      { id: SKIP_ID },
      { id: SKIP_ID },
      { id: UNDO_ID },
      { id: HINT_ID },
      { id: KEY_BASE + 2 },
    ];
    peek(s).syncItems(true);
    expect(s.available).toEqual({ skip: 2, undo: 1, hint: 1 });
    expect(s.unlockedWorlds.has(2)).toBe(true); // floor 0 by default -> own key suffices
  });

  it("skip consumes a token and routes to a real location check (no permanent stall)", () => {
    const { s, checked } = mockSession();
    peek(s).received.skip = 1;
    expect(s.useSkip(7)).toBe(true);
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelSolved(7)).toBe(true);
    expect(s.available.skip).toBe(0);
    expect(s.useSkip(7)).toBe(false); // already solved
    expect(s.useSkip(8)).toBe(false); // no tokens left
  });

  it("fires traps only for newly received items, not the suppressed connect backlog", () => {
    const traps: string[] = [];
    const { s, client } = mockSession((v) => traps.push(v));
    client.items.received = [{ id: TRAP_ID_BASE }];
    peek(s).syncItems(true); // connect-time backlog: suppressed
    expect(traps).toEqual([]);
    client.items.received.push({ id: TRAP_ID_BASE + 2 });
    peek(s).syncItems(false); // live: fire only the new one
    expect(traps).toEqual(["reversed"]);
  });

  it("useUndo / useHint consume their tokens", () => {
    const { s } = mockSession();
    peek(s).received.undo = 1;
    peek(s).received.hint = 1;
    expect(s.useUndo()).toBe(true);
    expect(s.useUndo()).toBe(false);
    expect(s.useHint()).toBe(true);
    expect(s.useHint()).toBe(false);
  });
});

describe("ap/session — Pull ability (expert logic)", () => {
  it("gates pulling until the Pull item is received", () => {
    const { s, client } = mockSession();
    peek(s).slot = sampleSlot({ pull_logic: true, requires_pull: { "21": true } });
    expect(s.canPull).toBe(false);
    expect(s.needsPull(21)).toBe(true);
    expect(s.needsPull(22)).toBe(false);
    client.items.received = [{ id: PULL_ID }];
    peek(s).syncItems(true);
    expect(s.canPull).toBe(true);
  });

  it("pulling is always available without expert logic", () => {
    const { s } = mockSession();
    peek(s).slot = sampleSlot({ pull_logic: false });
    expect(s.canPull).toBe(true);
    expect(s.needsPull(21)).toBe(false);
  });
});

describe("ap/session — par checks (Phase 4)", () => {
  it("sends the par check when within par and par_checks is on", () => {
    const { s, checked } = mockSession();
    peek(s).slot = sampleSlot({ par_checks: true, par: { "7": 10 } });
    s.reportSolved(7, 8); // 8 <= par 10
    expect(checked).toEqual([locationIdForLevel(7), locationIdForParLevel(7)]);
    expect(s.isLevelSolved(7)).toBe(true);
    expect(s.isLevelPar(7)).toBe(true);
  });

  it("sends only the solve check when over par", () => {
    const { s, checked } = mockSession();
    peek(s).slot = sampleSlot({ par_checks: true, par: { "7": 10 } });
    s.reportSolved(7, 12); // 12 > par 10
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelPar(7)).toBe(false);
  });

  it("never sends a par check when par_checks is off", () => {
    const { s, checked } = mockSession();
    peek(s).slot = sampleSlot({ par_checks: false, par: { "7": 10 } });
    s.reportSolved(7, 1);
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelPar(7)).toBe(false);
  });

  it("a skip clears the level but never counts as a par clear", () => {
    const { s, checked } = mockSession();
    peek(s).slot = sampleSlot({ par_checks: true, par: { "7": 10 } });
    peek(s).received.skip = 1;
    expect(s.useSkip(7)).toBe(true); // reportSolved called without a push count
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelSolved(7)).toBe(true);
    expect(s.isLevelPar(7)).toBe(false);
  });
});

describe("ap/ids — efficiency-location band", () => {
  it("round-trips efficiency-location id <-> level number, in its own band", () => {
    for (const n of [1, 2, 30, 155]) {
      expect(locationIdForEfficientLevel(n)).toBe(EFF_LOC_BASE + n);
      expect(levelForEfficientLocationId(locationIdForEfficientLevel(n))).toBe(n);
    }
    // No overlap with the solve or par bands.
    expect(levelForEfficientLocationId(locationIdForLevel(30))).toBeNull();
    expect(levelForEfficientLocationId(locationIdForParLevel(30))).toBeNull();
    expect(levelForEfficientLocationId(EFF_LOC_BASE)).toBeNull(); // n = 0
    expect(levelForEfficientLocationId(EFF_LOC_BASE + 156)).toBeNull();
  });
});

describe("ap/slotData — efficientThresholdForLevel", () => {
  it("is floor(par * (1 + margin/100))", () => {
    expect(
      efficientThresholdForLevel(sampleSlot({ par: { "7": 10 }, efficiency_margin: 15 }), 7),
    ).toBe(11);
    expect(
      efficientThresholdForLevel(sampleSlot({ par: { "7": 20 }, efficiency_margin: 25 }), 7),
    ).toBe(25);
  });

  it("equals par when the margin is 0 or absent", () => {
    expect(
      efficientThresholdForLevel(sampleSlot({ par: { "7": 10 }, efficiency_margin: 0 }), 7),
    ).toBe(10);
    expect(efficientThresholdForLevel(sampleSlot({ par: { "7": 10 } }), 7)).toBe(10);
  });

  it("is null when no par is shipped for the level", () => {
    expect(efficientThresholdForLevel(sampleSlot({ efficiency_margin: 15 }), 7)).toBeNull();
  });
});

describe("ap/session — efficiency tier", () => {
  const effSlot = (over: Partial<SlotData> = {}) =>
    sampleSlot({
      par_checks: true,
      efficiency_checks: true,
      efficiency_margin: 20,
      par: { "7": 10 },
      ...over,
    });

  it("a perfect solve fires solve + par + efficiency", () => {
    const { s, checked } = mockSession();
    peek(s).slot = effSlot();
    s.reportSolved(7, 9); // 9 <= par 10, also <= eff floor(10*1.2)=12
    expect(checked).toEqual([
      locationIdForLevel(7),
      locationIdForParLevel(7),
      locationIdForEfficientLevel(7),
    ]);
    expect(s.isLevelPar(7)).toBe(true);
    expect(s.isLevelEfficient(7)).toBe(true);
  });

  it("an efficient-but-not-perfect solve fires solve + efficiency only", () => {
    const { s, checked } = mockSession();
    peek(s).slot = effSlot();
    s.reportSolved(7, 12); // 12 > par 10 but <= eff 12
    expect(checked).toEqual([locationIdForLevel(7), locationIdForEfficientLevel(7)]);
    expect(s.isLevelPar(7)).toBe(false);
    expect(s.isLevelEfficient(7)).toBe(true);
  });

  it("an inefficient solve fires only the solve check", () => {
    const { s, checked } = mockSession();
    peek(s).slot = effSlot();
    s.reportSolved(7, 13); // 13 > eff 12
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelEfficient(7)).toBe(false);
  });

  it("a replay in fewer pushes upgrades efficient -> perfect (sends only the par check)", () => {
    const { s, checked } = mockSession();
    peek(s).slot = effSlot();
    s.reportSolved(7, 12); // first clear: efficient only (12 > par 10, <= eff 12)
    expect(s.isLevelPar(7)).toBe(false);
    expect(s.isLevelEfficient(7)).toBe(true);

    s.reportSolved(7, 10); // replay at exactly par -> upgrade to perfect
    expect(s.isLevelPar(7)).toBe(true);
    // The replay re-sends the idempotent solve check and the newly-earned par check,
    // but not a second efficiency check (already earned).
    expect(checked).toEqual([
      locationIdForLevel(7),
      locationIdForEfficientLevel(7),
      locationIdForLevel(7),
      locationIdForParLevel(7),
    ]);
  });

  it("never sends an efficiency check when the tier is off", () => {
    const { s, checked } = mockSession();
    peek(s).slot = sampleSlot({
      par_checks: true,
      efficiency_checks: false,
      efficiency_margin: 20,
      par: { "7": 10 },
    });
    s.reportSolved(7, 12);
    expect(checked).toEqual([locationIdForLevel(7)]);
    expect(s.isLevelEfficient(7)).toBe(false);
  });
});

describe("ap/session — play stats", () => {
  it("records visits (deduped per session) and solve events in memory", () => {
    const { s } = mockSession();
    peek(s).slot = sampleSlot();
    s.recordVisit(7);
    s.recordVisit(7); // same page-load session -> sessions deduped, visits still counts
    s.recordVisit(8);
    s.recordSolve(7, { moves: 40, pushes: 12, timeMs: 5000, ts: 1 });

    const seven = derive(s.statFor(7));
    expect(seven.visits).toBe(2);
    expect(seven.uniqueVisits).toBe(1);
    expect(seven.solveCount).toBe(1);
    expect(seven.bestMoves).toBe(40);
    expect(seven.bestPushes).toBe(12);
    expect(seven.bestTimeMs).toBe(5000);

    expect(derive(s.statFor(8)).visits).toBe(1);
    expect(s.statFor(99)).toBeUndefined();
  });

  it("keeps the best (min) across multiple solve events", () => {
    const { s } = mockSession();
    peek(s).slot = sampleSlot();
    s.recordSolve(7, { moves: 50, pushes: 14, timeMs: 9000, ts: 1 });
    s.recordSolve(7, { moves: 44, pushes: 12, timeMs: 7000, ts: 2 });
    const d = derive(s.statFor(7));
    expect(d.solveCount).toBe(2);
    expect(d.bestMoves).toBe(44);
    expect(d.bestPushes).toBe(12);
    expect(d.bestTimeMs).toBe(7000);
  });
});
