// Visibility + persistence for the Pull control, kept apart from main.ts so the decision is pure
// and unit-testable (the client tests run in node, with no DOM).

const SOLO_PULL_KEY = "sokopelago.solo.pull";

/**
 * Whether the Pull control should be offered to the player.
 *
 * - Multiworld (connected): only when the seed's `pull_logic` actually gates levels behind the
 *   Pull item. With pull_logic off (e.g. the curated pool) there is no Pull item to find, so the
 *   control would be a lie — hide it.
 * - Solo free-play: only when the player opted into Pull as a sandbox aid (default off).
 *
 * Pure: no module/DOM state, so it can be exercised directly in tests.
 */
export function pullControlVisible(opts: {
  connected: boolean;
  pullLogic: boolean;
  soloPullEnabled: boolean;
}): boolean {
  return opts.connected ? opts.pullLogic : opts.soloPullEnabled;
}

/** Load the persisted solo-pull opt-in (best-effort; defaults off). */
export function loadSoloPullEnabled(): boolean {
  try {
    return localStorage.getItem(SOLO_PULL_KEY) === "1";
  } catch {
    return false; // storage unavailable → treat as opted out
  }
}

/** Persist the solo-pull opt-in (best-effort). */
export function saveSoloPullEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(SOLO_PULL_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore unavailable storage */
  }
}
