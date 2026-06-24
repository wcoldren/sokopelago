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
  /** Merged pools (curated.json) tag each entry with its origin set as "<corpus>:<n>". */
  source?: string;
  /** Set on levels that can only be solved with the Pull ability (pullban). */
  requires_pull?: boolean;
}

/**
 * Resolve `<app-root>/data/<corpus>.json` from a JS bundle URL under `<app-root>/assets/`.
 *
 * The build copies the manifests to `<app-root>/data/` (sibling of the `assets/` dir Vite emits
 * bundles into), so `../data/<corpus>.json` resolved against the module's own URL lands at the app
 * root regardless of which page route is loading — the fix for the POTD page, served one level deep
 * at `/sokopelago/potd/`, where a route-relative `./data/...` used to 404. Assumes Vite's default
 * `assetsDir` (a direct child of `outDir`); the unit test pins this.
 */
export const dataUrlFromModule = (corpus: string, moduleUrl: string): string =>
  new URL(`../data/${corpus}.json`, moduleUrl).href;

/**
 * URL of a corpus manifest. Vite's `base` is relative (`"./"`) so the built site is portable (root
 * locally, `/sokopelago/` on GitHub Pages, inside an itch.io zip) — but a route-relative `./data/`
 * resolves wrong from a sub-route like `/potd/`. In the build we anchor to the module URL (under
 * `assets/`) so data always resolves at the app root; in the dev server modules live under `/src/`
 * (not a sibling of `/data`), where `BASE_URL` is the absolute `"/"` and already resolves correctly
 * from any route.
 */
export const manifestUrl = (corpus: string): string =>
  import.meta.env.DEV
    ? `${import.meta.env.BASE_URL}data/${corpus}.json`
    : dataUrlFromModule(corpus, import.meta.url);

/** Fetch + parse a corpus manifest by name. Throws on a non-OK response. */
export async function fetchManifest(corpus: string): Promise<ManifestEntry[]> {
  const url = manifestUrl(corpus);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`failed to load ${url}: ${res.status}`);
  return (await res.json()) as ManifestEntry[];
}
