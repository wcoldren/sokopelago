// slot_data emitted by the apworld's fill_slot_data (apworld/sokopelago/__init__.py),
// plus pure derivations the client uses to gate levels and detect its goal.
//
// Everything here is server-agnostic and unit-tested without a live connection.

export type GoalMode = "beat_final_region" | "solve_count" | "boss_level";

/** Shape of the dict returned by SokopelagoWorld.fill_slot_data. */
export interface SlotData {
  corpus: string;
  level_count: number;
  levels_per_region: number;
  /** Flat list of Microban level numbers included in this seed. */
  levels: number[];
  /** World index (as a string key) -> the Microban level numbers in it. */
  region_map: Record<string, number[]>;
  goal: GoalMode;
  goal_solve_count: number;
  goal_boss_level: number;
  /** Index of the final/highest world (= region count). */
  final_world: number;
  /** Push-par per seed level (Microban number as a string key). */
  par?: Record<string, number>;
  /** Normalized 0..1 difficulty per seed level (Microban number as a string key). */
  difficulty?: Record<string, number>;
  seed_name: string;
  player_name: string;
  player_id: number;
}

/** Map each Microban level number to the world index that contains it. */
export function worldOfLevel(slot: SlotData): Map<number, number> {
  const map = new Map<number, number>();
  for (const [world, levels] of Object.entries(slot.region_map)) {
    const wi = Number(world);
    for (const n of levels) map.set(n, wi);
  }
  return map;
}

/** Microban level numbers in a given world (empty if the world is unknown). */
export function levelsInWorld(slot: SlotData, world: number): number[] {
  return slot.region_map[String(world)] ?? [];
}

/** How many of this seed's levels are in `solved`. */
export function solvedInSeed(slot: SlotData, solved: ReadonlySet<number>): number {
  let count = 0;
  for (const n of slot.levels) if (solved.has(n)) count++;
  return count;
}

/**
 * Whether the client-side win condition is met. The client (not the generator)
 * enforces the real goal:
 *   - beat_final_region: every level in the final world is solved
 *   - solve_count:       at least goal_solve_count seed levels are solved
 *   - boss_level:        the designated boss level is solved
 */
export function isGoalMet(slot: SlotData, solved: ReadonlySet<number>): boolean {
  switch (slot.goal) {
    case "solve_count":
      return solvedInSeed(slot, solved) >= slot.goal_solve_count;
    case "boss_level":
      return solved.has(slot.goal_boss_level);
    case "beat_final_region":
    default:
      return levelsInWorld(slot, slot.final_world).every((n) => solved.has(n));
  }
}
