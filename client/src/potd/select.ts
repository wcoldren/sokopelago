// Puzzle-of-the-Day selection: a pure function of the UTC calendar day, so every client
// worldwide gets the same puzzle and it rolls over at 00:00 UTC. We seed a small deterministic
// PRNG with the UTC date string and index the pool with it — deliberately NOT `dayIndex % len`,
// which would march predictably up the list. No backend is involved in selection.

/** The UTC calendar day of `date` as `YYYY-MM-DD`. Uses UTC accessors, so the result is
 *  timezone-independent — the same instant yields the same string in every locale. */
export function utcDayString(date: Date): string {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** xmur3 string hash → a 32-bit seed generator (one good seed per call). */
function xmur3(str: string): () => number {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return h >>> 0;
  };
}

/** mulberry32 PRNG: a 32-bit seed → a function yielding floats in [0, 1). */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * The pool index (0-based) for a given UTC day string, deterministic across clients and
 * timezone-independent (the day string is already UTC). Returns 0 for an empty pool.
 */
export function pickDailyIndex(dateStr: string, poolSize: number): number {
  if (poolSize <= 0) return 0;
  const seed = xmur3(dateStr)();
  const rand = mulberry32(seed)();
  return Math.floor(rand * poolSize);
}

/** Convenience: today's pool index for the given pool size (UTC day of `now`). */
export function todaysIndex(poolSize: number, now: Date): number {
  return pickDailyIndex(utcDayString(now), poolSize);
}
