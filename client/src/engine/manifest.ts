// Shared corpus-manifest access used by every page (main play loop + POTD). The client
// renders from per-corpus manifests baked by tools/build_corpus.py into
// apworld/sokopelago/data/<corpus>.json and copied to /data by Vite (see vite.config.ts).

/** One level entry in a bundled corpus manifest (data/<corpus>.json). */
export interface ManifestEntry {
  n: number;
  name: string;
  board: string[];
  solution?: string;
  par?: number;
  difficulty?: number;
}

/**
 * URL of a corpus manifest, base-relative so the fetch resolves under whatever path the
 * site is served from (root locally, /sokopelago/ on GitHub Pages, inside an itch.io zip).
 * BASE_URL is the Vite `base` ("./").
 */
export const manifestUrl = (corpus: string): string =>
  `${import.meta.env.BASE_URL}data/${corpus}.json`;

/** Fetch + parse a corpus manifest by name. Throws on a non-OK response. */
export async function fetchManifest(corpus: string): Promise<ManifestEntry[]> {
  const url = manifestUrl(corpus);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`failed to load ${url}: ${res.status}`);
  return (await res.json()) as ManifestEntry[];
}
