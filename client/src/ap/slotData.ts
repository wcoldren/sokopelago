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
  /** 0.7 accurate logic: per-world key-count floor (world index as a string key). A world
   * unlocks when its own key is held AND the total number of keys held is >= this floor.
   * All-zero (flat single-key unlock) for non-beat_final_region goals; absent on pre-0.7
   * seeds (then treated as 0). */
  chain_floors?: Record<string, number>;
  /** 0.7 accurate logic: when true, the final_world (boss zone) unlocks only once ALL keys
   * are held. Set only for beat_final_region seeds with more than one world. */
  boss_all_keys?: boolean;
  /** Push-par per seed level (Microban number as a string key). */
  par?: Record<string, number>;
  /** Normalized 0..1 difficulty per seed level (Microban number as a string key). */
  difficulty?: Record<string, number>;
  /** When true, the seed has par-location checks; solving within par sends a second check. */
  par_checks?: boolean;
  /** When true, the seed also has the efficiency tier; solving within the margin over
   * optimal sends a third check. Only meaningful alongside par_checks. */
  efficiency_checks?: boolean;
  /** Percent over the optimal push count that still counts as an efficient solve. */
  efficiency_margin?: number;
  /** Pull Logic: when true, requires_pull levels are gated behind the Pull item. */
  pull_logic?: boolean;
  /** Level numbers (string keys) that need the Pull ability to be solved. */
  requires_pull?: Record<string, boolean>;
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

/**
 * 1-based position of level `n` within its world's region order (the order the picker shows),
 * or 0 if it isn't in any world. Lets the UI label levels per world ("World 2 · L3") instead
 * of by raw Microban corpus number, which jumps around under shuffled selection.
 */
export function seedPositionInWorld(slot: SlotData, n: number): number {
  for (const levels of Object.values(slot.region_map)) {
    const i = levels.indexOf(n);
    if (i >= 0) return i + 1;
  }
  return 0;
}

/**
 * The next level to auto-advance to after solving `afterN`, in world-first order: the rest of
 * the current world, then forward (higher-index) worlds, then wrapping back to earlier worlds
 * (and finally earlier levels of the current world). The first candidate that is playable and
 * unsolved wins; `null` when nothing remains. Pure — the caller passes `isSolved`/`isPlayable`
 * predicates (so it stays unit-testable without a live Session).
 */
export function nextLevelInWorldOrder(
  slot: SlotData,
  afterN: number,
  isSolved: (n: number) => boolean,
  isPlayable: (n: number) => boolean,
): number | null {
  const worlds = Object.keys(slot.region_map)
    .map(Number)
    .sort((a, b) => a - b);
  if (worlds.length === 0) return null;
  // Locate the current level's world + position (fall back to "before the first world").
  let w0 = worlds[0];
  let p0 = -1;
  for (const w of worlds) {
    const i = levelsInWorld(slot, w).indexOf(afterN);
    if (i >= 0) {
      w0 = w;
      p0 = i;
      break;
    }
  }
  const cur = levelsInWorld(slot, w0);
  const ordered: number[] = [
    ...cur.slice(p0 + 1), // rest of the current world
    ...worlds.filter((w) => w > w0).flatMap((w) => levelsInWorld(slot, w)), // forward worlds
    ...worlds.filter((w) => w < w0).flatMap((w) => levelsInWorld(slot, w)), // wrap to earlier worlds
    ...cur.slice(0, p0 + 1), // wrap within the current world (afterN itself is skipped: it's solved)
  ];
  return ordered.find((n) => isPlayable(n) && !isSolved(n)) ?? null;
}

/**
 * Key-count floor for a world: a world unlocks when its own key is held AND the total
 * number of keys held is >= this floor. Defaults to 0 (flat single-key unlock) when no
 * floor was shipped, so pre-0.7 seeds and non-chained goals behave exactly as before.
 */
export function chainFloor(slot: SlotData, world: number): number {
  const f = slot.chain_floors?.[String(world)];
  return typeof f === "number" && f >= 0 ? f : 0;
}

/** Push-par for a level, or `null` if unknown (no par data shipped for it). */
export function parForLevel(slot: SlotData, n: number): number | null {
  const par = slot.par?.[String(n)];
  return typeof par === "number" && par > 0 ? par : null;
}

/**
 * Push threshold for the efficient tier of a level, or `null` if unknown. Solving in
 * `<= ` this many pushes sends the efficiency check (whereas exactly the par count sends
 * the perfect tier). Equals `floor(par * (1 + margin/100))`.
 */
export function efficientThresholdForLevel(slot: SlotData, n: number): number | null {
  const par = parForLevel(slot, n);
  if (par === null) return null;
  const margin = typeof slot.efficiency_margin === "number" ? slot.efficiency_margin : 0;
  return Math.floor(par * (1 + margin / 100));
}

/** Normalized 0..1 difficulty for a level, or `null` if none was shipped. */
export function difficultyForLevel(slot: SlotData, n: number): number | null {
  const d = slot.difficulty?.[String(n)];
  return typeof d === "number" && d >= 0 ? d : null;
}

/** Whether level `n` needs the Pull ability (only meaningful under expert logic). */
export function requiresPull(slot: SlotData, n: number): boolean {
  return slot.requires_pull?.[String(n)] === true;
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
