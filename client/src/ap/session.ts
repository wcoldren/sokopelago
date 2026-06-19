// Runtime Archipelago session: a thin wrapper over archipelago.js that holds
// Sokopelago's unlock/solve state and drives checks + the goal report.
//
// The library owns the protocol (handshake, item indexing, ReceivedItems,
// LocationChecks, reconnection, PrintJSON). This module owns the game wiring:
// world keys -> unlocked worlds, solved levels -> checks, goal -> StatusUpdate.

import { Client, itemsHandlingFlags, type Item } from "archipelago.js";

import { levelForLocationId, locationIdForLevel, worldForKeyItem } from "./ids";
import { isGoalMet, worldOfLevel, type SlotData } from "./slotData";

/** UI hooks the play loop subscribes to. */
export interface SessionCallbacks {
  /** Authenticated; slot_data is available and the seed's levels are known. */
  onConnected: (slot: SlotData) => void;
  /** Unlocked worlds and/or solved levels changed — refresh the selector. */
  onUpdate: () => void;
  /** The client-side goal was just met (GOAL already sent to the server). */
  onGoal: () => void;
  /** A server message arrived (chat / item routing) — show it in the status line. */
  onMessage: (text: string) => void;
  /** The socket dropped (intentionally or not). */
  onDisconnect: () => void;
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

export class Session {
  private readonly client = new Client();
  private readonly cb: SessionCallbacks;

  slot: SlotData | null = null;
  /** World 1 is always free; keyed worlds are added as their keys arrive. */
  readonly unlockedWorlds = new Set<number>([1]);
  readonly solvedLevels = new Set<number>();

  private worldOf = new Map<number, number>();
  private goaled = false;

  constructor(cb: SessionCallbacks) {
    this.cb = cb;
  }

  /**
   * Connect and authenticate. `host` may be a bare `host:port` (defaults to the
   * AP port 38281) or include a `ws://` / `wss://` scheme; archipelago.js tries
   * wss then falls back to ws when the scheme is omitted.
   */
  async connect(host: string, slot: string, password?: string): Promise<void> {
    // Register listeners before login so the connection backlog is captured.
    this.client.items.on("itemsReceived", (items) => this.handleItems(items));
    this.client.room.on("locationsChecked", (locs) => this.handleChecked(locs));
    this.client.messages.on("message", (text) => this.cb.onMessage(text));
    this.client.socket.on("disconnected", () => this.cb.onDisconnect());

    // login's generic requires a JSONRecord index signature; our SlotData is a
    // closed shape, so take the raw record and narrow it.
    const raw = await this.client.login(host, slot, "Sokopelago", {
      items: itemsHandlingFlags.all, // 7 — must receive our own world keys
      slotData: true,
      password: password || "",
    });
    const slotData = raw as unknown as SlotData;

    this.slot = slotData;
    this.worldOf = worldOfLevel(slotData);

    // Re-seed from current state in case events fired during login().
    this.handleItems(this.client.items.received);
    this.handleChecked(this.client.room.checkedLocations);

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

  isLevelSolved(n: number): boolean {
    return this.solvedLevels.has(n);
  }

  worldForLevel(n: number): number | undefined {
    return this.worldOf.get(n);
  }

  /** Report a solved level: send the location check and re-check the goal. */
  reportSolved(n: number): void {
    if (!this.client.authenticated) return;
    this.client.check(locationIdForLevel(n));
    this.solvedLevels.add(n); // optimistic; the server echo is idempotent
    this.maybeGoal();
  }

  private handleItems(items: Item[]): void {
    let changed = false;
    for (const item of items) {
      const w = worldForKeyItem(item.id);
      if (w !== null && !this.unlockedWorlds.has(w)) {
        this.unlockedWorlds.add(w);
        changed = true;
      }
    }
    if (changed) this.cb.onUpdate();
  }

  private handleChecked(locations: number[]): void {
    let changed = false;
    for (const id of locations) {
      const n = levelForLocationId(id);
      if (n !== null && !this.solvedLevels.has(n)) {
        this.solvedLevels.add(n);
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
