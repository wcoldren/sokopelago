// Network ID arithmetic for the Sokopelago apworld contract.
//
// These offsets are fixed by the shipped apworld and must not drift:
//   apworld/sokopelago/Items.py      -> KEY_BASE / FILLER_ID
//   apworld/sokopelago/Locations.py  -> LOC_BASE
//
// Microban level n (1-based) <-> client Level.index n-1 (parse order).

/** Base id for `World n Key` items: id = KEY_BASE + n (n = 2..MAX_WORLDS). */
export const KEY_BASE = 9_750_000;
/** Id of the `Sokoban Token` filler item (KEY_BASE + 1, i.e. the "World 1" slot). */
export const FILLER_ID = 9_750_001;
/** Base id for `Solve Microban n` locations: id = LOC_BASE + n (n = 1..MAX_LEVELS). */
export const LOC_BASE = 9_760_000;

// Escape-valve / trap item ids — fixed by apworld/sokopelago/Items.py, in a band
// clear of the key range (KEY_BASE + 2..155) and the location range (LOC_BASE+).
export const SKIP_ID = 9_750_200;
export const UNDO_ID = 9_750_201;
export const HINT_ID = 9_750_202;
export const TRAP_ID_BASE = 9_750_300;
/** Trap variants, indexed by `id - TRAP_ID_BASE` (matches Items.TRAP_ITEM_NAMES). */
export const TRAP_VARIANTS = ["scramble", "decoy", "reversed"] as const;
export type TrapVariant = (typeof TRAP_VARIANTS)[number];

export type ValveKind = "skip" | "undo" | "hint" | "trap";
export interface ValveItem {
  kind: ValveKind;
  /** Present only when `kind === "trap"`. */
  trap?: TrapVariant;
}

/** Classify a received item id as an escape valve / trap, or `null` if it is neither. */
export function escapeValveForItem(id: number): ValveItem | null {
  if (id === SKIP_ID) return { kind: "skip" };
  if (id === UNDO_ID) return { kind: "undo" };
  if (id === HINT_ID) return { kind: "hint" };
  const t = id - TRAP_ID_BASE;
  if (t >= 0 && t < TRAP_VARIANTS.length) return { kind: "trap", trap: TRAP_VARIANTS[t] };
  return null;
}

/** Microban corpus size; the apworld caps worlds and levels at this count. */
export const MAX_LEVELS = 155;
export const MAX_WORLDS = 155;

/** Location id the client checks when Microban level `n` is solved. */
export function locationIdForLevel(n: number): number {
  return LOC_BASE + n;
}

/**
 * Microban level number for a location id, or `null` if the id is not a
 * Sokopelago solve-location.
 */
export function levelForLocationId(id: number): number | null {
  const n = id - LOC_BASE;
  return n >= 1 && n <= MAX_LEVELS ? n : null;
}

/**
 * World index unlocked by a received item id, or `null` if the item is not a
 * world key (e.g. the `Sokoban Token` filler, whose id maps to the keyless
 * World 1 slot).
 */
export function worldForKeyItem(id: number): number | null {
  const w = id - KEY_BASE;
  return w >= 2 && w <= MAX_WORLDS ? w : null;
}
