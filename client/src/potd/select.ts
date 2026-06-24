// Puzzle-of-the-Day selection: a pure function of the UTC calendar day, so every client worldwide
// gets the same puzzle and it rolls over at 00:00 UTC. We walk a fixed deterministic PERMUTATION of
// the pool by day number — so there is no repeat until the whole pool is exhausted (any window of
// `poolSize` consecutive days shows each puzzle exactly once), and never a predictable `day % len`
// march. After a full cycle the same order repeats. No backend is involved in selection.
//
// If the pool size changes (the corpus grows), the schedule simply re-derives — there's no
// persisted day↔puzzle contract.

/** The UTC calendar day of `date` as `YYYY-MM-DD`. Uses UTC accessors, so the result is
 *  timezone-independent — the same instant yields the same string in every locale. */
export function utcDayString(date: Date): string {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Whole UTC days since the Unix epoch for a `YYYY-MM-DD` string (timezone-independent). */
export function dayNumber(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  return Math.floor(Date.UTC(y, m - 1, d) / 86_400_000);
}

/** xmur3 string hash → a 32-bit seed generator (one good seed per call). */
export function xmur3(str: string): () => number {
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

// A fixed, deterministic permutation of [0, poolSize) — the daily schedule. Constant seed so every
// client derives the same order; memoized per pool size (the only thing that changes it).
const PERMUTATION_SEED = "sokopelago-potd/1";
const permCache = new Map<number, number[]>();
function permutation(poolSize: number): number[] {
  const cached = permCache.get(poolSize);
  if (cached) return cached;
  const perm = Array.from({ length: poolSize }, (_, i) => i);
  const rng = mulberry32(xmur3(PERMUTATION_SEED)());
  for (let i = poolSize - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1)); // Fisher–Yates
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  permCache.set(poolSize, perm);
  return perm;
}

/**
 * The pool index (0-based) for a given UTC day string: `permutation[dayNumber mod poolSize]`.
 * Deterministic across clients and timezone-independent. No repeat until the pool is exhausted.
 * Returns 0 for an empty pool.
 */
export function pickDailyIndex(dateStr: string, poolSize: number): number {
  if (poolSize <= 0) return 0;
  const pos = ((dayNumber(dateStr) % poolSize) + poolSize) % poolSize; // non-negative
  return permutation(poolSize)[pos];
}

/** Convenience: today's pool index for the given pool size (UTC day of `now`). */
export function todaysIndex(poolSize: number, now: Date): number {
  return pickDailyIndex(utcDayString(now), poolSize);
}
