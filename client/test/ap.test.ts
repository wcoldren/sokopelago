import { describe, expect, it } from "vitest";

import {
  FILLER_ID,
  KEY_BASE,
  LOC_BASE,
  levelForLocationId,
  locationIdForLevel,
  worldForKeyItem,
} from "../src/ap/ids";
import {
  isGoalMet,
  levelsInWorld,
  solvedInSeed,
  worldOfLevel,
  type SlotData,
} from "../src/ap/slotData";
import { resolveServerUrl } from "../src/ap/session";

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
