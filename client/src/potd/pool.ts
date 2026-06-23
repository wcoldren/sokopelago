// Puzzle-of-the-Day pool: derive the daily-eligible puzzle list from the bundled `curated`
// manifest, plus the small identity helper that hangs off a visitorId. Pure + deterministic, so
// every client of a given build agrees on the pool (and so it's all unit-testable).
//
// The daily pool is the curated cross-corpus pool (Microban I–III, Sasquatch, XSokoban, …)
// restricted to push-solvable puzzles: we drop the generated `autoban` set and the whole `pullban`
// set (its pull-gated levels need a Pull control the POTD page doesn't have), plus any explicitly
// pull-required level.

import type { ManifestEntry } from "../engine/manifest";
import { xmur3 } from "./select";

/** Source corpora excluded from the daily pool. */
const EXCLUDED_SOURCE_CORPORA = new Set(["autoban", "pullban"]);

/** A curated entry's `source` is "<corpus>:<n>" (e.g. "sasquatch7:33"), naming the origin set and
 * its number there. Falls back to ("curated", `fallbackN`) when the tag is missing or malformed. */
export function parseSource(
  source: string | undefined,
  fallbackN: number,
): { corpus: string; n: number } {
  if (source) {
    const i = source.lastIndexOf(":");
    if (i > 0) {
      const n = Number(source.slice(i + 1));
      if (Number.isInteger(n) && n >= 1) return { corpus: source.slice(0, i), n };
    }
  }
  return { corpus: "curated", n: fallbackN };
}

/** The daily-eligible puzzles: the curated manifest minus the excluded source corpora and any
 * pull-required level, preserving manifest order so the index→puzzle map is stable across clients. */
export function buildDailyPool(entries: ManifestEntry[]): ManifestEntry[] {
  return entries.filter((e) => {
    if (e.requires_pull) return false;
    return !EXCLUDED_SOURCE_CORPORA.has(parseSource(e.source, e.n).corpus);
  });
}

/** A short, stable, non-secret suffix from a visitorId (first 4 hex of an xmur3 hash), so two
 * players who happen to pick the same handle still render distinctly (e.g. "bob·a3f1"). Identity
 * is the visitorId; the handle is only a display label. */
export function handleSuffix(visitorId: string): string {
  return (xmur3(visitorId)() >>> 0).toString(16).padStart(8, "0").slice(0, 4);
}

/** "bob·a3f1" — a handle with its visitor-derived suffix appended. */
export function handleDisplay(handle: string, visitorId: string): string {
  return `${handle}·${handleSuffix(visitorId)}`;
}
