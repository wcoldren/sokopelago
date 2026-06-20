// Runtime Archipelago session: a thin wrapper over archipelago.js that holds
// Sokopelago's unlock/solve state and drives checks + the goal report.
//
// The library owns the protocol (handshake, item indexing, ReceivedItems,
// LocationChecks, reconnection, PrintJSON). This module owns the game wiring:
// world keys -> unlocked worlds, solved levels -> checks, goal -> StatusUpdate.

import { Client, itemsHandlingFlags } from "archipelago.js";

import {
  escapeValveForItem,
  isPullItem,
  levelForLocationId,
  levelForParLocationId,
  locationIdForLevel,
  locationIdForParLevel,
  worldForKeyItem,
  type TrapVariant,
} from "./ids";
import { isGoalMet, parForLevel, requiresPull, worldOfLevel, type SlotData } from "./slotData";

/** UI hooks the play loop subscribes to. */
export interface SessionCallbacks {
  /** Authenticated; slot_data is available and the seed's levels are known. */
  onConnected: (slot: SlotData) => void;
  /** Unlocked worlds, solved levels, or token inventory changed — refresh the UI. */
  onUpdate: () => void;
  /** The client-side goal was just met (GOAL already sent to the server). */
  onGoal: () => void;
  /** A server message arrived (chat / item routing) — show it in the status line. */
  onMessage: (text: string) => void;
  /** A newly-received trap should fire its (presentation-only) effect. */
  onTrap: (variant: TrapVariant) => void;
  /** The socket dropped (intentionally or not). */
  onDisconnect: () => void;
}

/** Counts of the consumable escape-valve items. */
export interface ValveCounts {
  skip: number;
  undo: number;
  hint: number;
}

export interface ConnectPrefs {
  host: string;
  slot: string;
}

const PREFS_KEY = "sokopelago.ap.prefs";

/** Load the last-used host/slot for the connect form (best-effort). */
export function loadPrefs(): ConnectPrefs | null {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<ConnectPrefs>;
    if (typeof p.host === "string" && typeof p.slot === "string") {
      return { host: p.host, slot: p.slot };
    }
  } catch {
    /* ignore malformed/unavailable storage */
  }
  return null;
}

function savePrefs(prefs: ConnectPrefs): void {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore unavailable storage */
  }
}

/**
 * Resolve the websocket URL from a user-entered host.
 *
 * An explicit `ws://`/`wss://` scheme is honored as-is. For a bare host we
 * default local/self-hosted servers (which serve plain `ws`) to `ws://` —
 * browsers don't reliably fall back from a failed `wss` TLS handshake to `ws`,
 * so leaving it bare (which makes archipelago.js try `wss` first) fails against
 * a local MultiServer. Remote hosts are left bare so the library tries `wss`
 * then `ws`.
 */
export function resolveServerUrl(host: string): string {
  const trimmed = host.trim();
  if (/^wss?:\/\//i.test(trimmed)) return trimmed;
  const hostname = trimmed.replace(/^\[/, "").split(/[:\]]/)[0].toLowerCase();
  const isLocal =
    hostname === "localhost" ||
    hostname === "0.0.0.0" ||
    hostname === "::1" ||
    hostname.startsWith("127.") ||
    hostname.startsWith("192.168.") ||
    hostname.startsWith("10.") ||
    hostname.endsWith(".local");
  return isLocal ? `ws://${trimmed}` : trimmed;
}

export class Session {
  private readonly client = new Client();
  private readonly cb: SessionCallbacks;

  slot: SlotData | null = null;
  /** World 1 is always free; keyed worlds are added as their keys arrive. */
  readonly unlockedWorlds = new Set<number>([1]);
  readonly solvedLevels = new Set<number>();
  /** Levels solved within par (the par-location check was sent). For the UI / restore. */
  readonly parLevels = new Set<number>();

  private worldOf = new Map<number, number>();
  private goaled = false;
  /** Whether the Pull ability item has been received (expert logic). */
  private pullReceived = false;

  // Escape-valve inventory. `received` is recomputed from the full item backlog
  // (idempotent across reconnects); `consumed` is persisted to DataStorage because
  // there is no server echo for using a token. available = received - consumed.
  private ready = false;
  private seenItemCount = 0;
  private readonly received: ValveCounts = { skip: 0, undo: 0, hint: 0 };
  private readonly consumed: ValveCounts = { skip: 0, undo: 0, hint: 0 };

  constructor(cb: SessionCallbacks) {
    this.cb = cb;
  }

  /**
   * Connect and authenticate. `host` may be a bare `host:port` (defaults to the
   * AP port 38281) or include a `ws://` / `wss://` scheme; archipelago.js tries
   * wss then falls back to ws when the scheme is omitted.
   */
  async connect(host: string, slot: string, password?: string): Promise<void> {
    // Register listeners before login so the connection backlog is captured. Live
    // item events are ignored until the connect-time backlog has been seeded (`ready`),
    // so past traps don't re-fire on reconnect.
    this.client.items.on("itemsReceived", () => {
      if (this.ready) this.syncItems(false);
    });
    this.client.room.on("locationsChecked", (locs) => this.handleChecked(locs));
    this.client.messages.on("message", (text) => this.cb.onMessage(text));
    this.client.socket.on("disconnected", () => this.cb.onDisconnect());

    // login's generic requires a JSONRecord index signature; our SlotData is a
    // closed shape, so take the raw record and narrow it.
    const raw = await this.client.login(resolveServerUrl(host), slot, "Sokopelago", {
      items: itemsHandlingFlags.all, // 7 — must receive our own world keys
      slotData: true,
      password: password || "",
    });
    const slotData = raw as unknown as SlotData;

    this.slot = slotData;
    this.worldOf = worldOfLevel(slotData);

    // Seed from current state: load consumed-token counts, then tally the item backlog
    // (suppressing trap effects for already-received traps) and restore solved levels.
    await this.loadConsumed();
    this.syncItems(true);
    this.handleChecked(this.client.room.checkedLocations);
    this.ready = true;

    savePrefs({ host, slot });
    this.cb.onConnected(slotData);
    this.maybeGoal();
  }

  disconnect(): void {
    this.client.socket.disconnect();
  }

  get authenticated(): boolean {
    return this.client.authenticated;
  }

  isLevelUnlocked(n: number): boolean {
    const w = this.worldOf.get(n);
    return w !== undefined && this.unlockedWorlds.has(w);
  }

  /** Whether the pull mechanic is available: always, unless expert logic gates it behind
   * the (not-yet-received) Pull ability. */
  get canPull(): boolean {
    return !this.slot?.expert_logic || this.pullReceived;
  }

  /** Whether level `n` needs the Pull ability under this seed's expert logic. */
  needsPull(n: number): boolean {
    return Boolean(this.slot?.expert_logic) && this.slot !== null && requiresPull(this.slot, n);
  }

  /** Playable = the world key is held AND (no pull gate, or Pull has been received). */
  isLevelPlayable(n: number): boolean {
    return this.isLevelUnlocked(n) && (this.canPull || !this.needsPull(n));
  }

  isLevelSolved(n: number): boolean {
    return this.solvedLevels.has(n);
  }

  /** Whether level `n` was solved within par (its par check was sent). */
  isLevelPar(n: number): boolean {
    return this.parLevels.has(n);
  }

  worldForLevel(n: number): number | undefined {
    return this.worldOf.get(n);
  }

  /**
   * Report a solved level: send its location check and re-check the goal. When the
   * seed has Par Checks and `pushCount` is within the level's push-par, also send the
   * parallel par-location check. `pushCount` is omitted for a Skip Token (skipping
   * clears the level but never counts as a par clear).
   */
  reportSolved(n: number, pushCount?: number): void {
    if (!this.client.authenticated) return;
    this.client.check(locationIdForLevel(n));
    this.solvedLevels.add(n); // optimistic; the server echo is idempotent
    if (this.slot?.par_checks && pushCount !== undefined && !this.parLevels.has(n)) {
      const par = parForLevel(this.slot, n);
      if (par !== null && pushCount <= par) {
        this.client.check(locationIdForParLevel(n));
        this.parLevels.add(n);
      }
    }
    this.maybeGoal();
  }

  /** Currently-available escape-valve tokens (received minus consumed). */
  get available(): ValveCounts {
    return {
      skip: Math.max(0, this.received.skip - this.consumed.skip),
      undo: Math.max(0, this.received.undo - this.consumed.undo),
      hint: Math.max(0, this.received.hint - this.consumed.hint),
    };
  }

  /** Consume a Skip Token to mark level `n` solved (sends the check). Returns false
   * if already solved or no token is available — guarantees a stuck level can clear. */
  useSkip(n: number): boolean {
    if (this.isLevelSolved(n) || !this.consume("skip")) return false;
    this.reportSolved(n);
    return true;
  }

  /** Consume an Undo Charge (the caller performs the board undo). */
  useUndo(): boolean {
    return this.consume("undo");
  }

  /** Consume a Hint Token (the caller reveals the move). */
  useHint(): boolean {
    return this.consume("hint");
  }

  private consume(kind: keyof ValveCounts): boolean {
    if (this.available[kind] <= 0) return false;
    this.consumed[kind] += 1;
    this.persistConsumed(kind);
    this.cb.onUpdate();
    return true;
  }

  /** Recompute valve inventory + world unlocks from the full item backlog (idempotent),
   * firing trap effects only for items received since the last sync. */
  private syncItems(suppressTraps: boolean): void {
    const received = this.client.items.received;
    let skip = 0;
    let undo = 0;
    let hint = 0;
    for (const item of received) {
      const w = worldForKeyItem(item.id);
      if (w !== null) {
        this.unlockedWorlds.add(w);
        continue;
      }
      if (isPullItem(item.id)) {
        this.pullReceived = true;
        continue;
      }
      const valve = escapeValveForItem(item.id);
      if (valve?.kind === "skip") skip += 1;
      else if (valve?.kind === "undo") undo += 1;
      else if (valve?.kind === "hint") hint += 1;
    }
    this.received.skip = skip;
    this.received.undo = undo;
    this.received.hint = hint;

    if (!suppressTraps) {
      for (let i = this.seenItemCount; i < received.length; i++) {
        const valve = escapeValveForItem(received[i].id);
        if (valve?.kind === "trap" && valve.trap) this.cb.onTrap(valve.trap);
      }
    }
    this.seenItemCount = received.length;
    this.cb.onUpdate();
  }

  private storageKey(kind: keyof ValveCounts): string {
    const s = this.slot;
    // Scope by seed + slot so concurrent worlds don't clobber each other's counters.
    return `sokopelago:${s?.seed_name ?? ""}:${s?.player_id ?? 0}:consumed:${kind}`;
  }

  private async loadConsumed(): Promise<void> {
    const keys = (["skip", "undo", "hint"] as const).map((k) => this.storageKey(k));
    try {
      const data = await this.client.storage.fetch<Record<string, number>>(keys, true);
      this.consumed.skip = Number(data[this.storageKey("skip")] ?? 0);
      this.consumed.undo = Number(data[this.storageKey("undo")] ?? 0);
      this.consumed.hint = Number(data[this.storageKey("hint")] ?? 0);
    } catch {
      /* storage unavailable — treat nothing as consumed yet */
    }
  }

  private persistConsumed(kind: keyof ValveCounts): void {
    if (!this.slot) return;
    void this.client.storage.prepare(this.storageKey(kind), 0).add(1).commit();
  }

  private handleChecked(locations: number[]): void {
    let changed = false;
    for (const id of locations) {
      const n = levelForLocationId(id);
      if (n !== null && !this.solvedLevels.has(n)) {
        this.solvedLevels.add(n);
        changed = true;
      }
      // A par-location check implies the level was solved within par; mark both so the
      // par badge and solved state survive a reconnect.
      const pn = levelForParLocationId(id);
      if (pn !== null) {
        if (!this.solvedLevels.has(pn)) this.solvedLevels.add(pn);
        if (!this.parLevels.has(pn)) this.parLevels.add(pn);
        changed = true;
      }
    }
    if (changed) {
      this.cb.onUpdate();
      this.maybeGoal();
    }
  }

  private maybeGoal(): void {
    if (this.goaled || !this.slot) return;
    if (isGoalMet(this.slot, this.solvedLevels)) {
      this.goaled = true;
      this.client.goal(); // StatusUpdate GOAL (30); once set it cannot change
      this.cb.onGoal();
    }
  }
}
