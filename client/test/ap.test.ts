import { describe, expect, it } from "vitest";

import {
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
  levelForLocationId,
  levelForParLocationId,
  locationIdForLevel,
  locationIdForParLevel,
  worldForKeyItem,
} from "../src/ap/ids";
import {
  difficultyForLevel,
  isGoalMet,
  levelsInWorld,
  parForLevel,
  requiresPull,
  solvedInSeed,
  worldOfLevel,
  type SlotData,
} from "../src/ap/slotData";
import { resolveServerUrl, Session, type SessionCallbacks } from "../src/ap/session";

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
    const slot = sampleSlot({ expert_logic: true, requires_pull: { "21": true } });
    expect(requiresPull(slot, 21)).toBe(true);
    expect(requiresPull(slot, 22)).toBe(false);
    expect(requiresPull(sampleSlot(), 21)).toBe(false); // no map at all
  });
});

// The session is a thin wrapper over archipelago.js; we inject a stub client to
// exercise inventory tallying, the skip->check routing invariant, and trap firing.
interface SessionInternals {
  client: unknown;
  slot: SlotData | null;
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
    client.items.received = [
      { id: SKIP_ID },
      { id: SKIP_ID },
      { id: UNDO_ID },
      { id: HINT_ID },
      { id: KEY_BASE + 2 },
    ];
    peek(s).syncItems(true);
    expect(s.available).toEqual({ skip: 2, undo: 1, hint: 1 });
    expect(s.unlockedWorlds.has(2)).toBe(true);
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
    peek(s).slot = sampleSlot({ expert_logic: true, requires_pull: { "21": true } });
    expect(s.canPull).toBe(false);
    expect(s.needsPull(21)).toBe(true);
    expect(s.needsPull(22)).toBe(false);
    client.items.received = [{ id: PULL_ID }];
    peek(s).syncItems(true);
    expect(s.canPull).toBe(true);
  });

  it("pulling is always available without expert logic", () => {
    const { s } = mockSession();
    peek(s).slot = sampleSlot({ expert_logic: false });
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
