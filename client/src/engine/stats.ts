// Per-level play statistics: visit counts + a per-solve event log, kept in BOTH solo
// free-play (localStorage, here) and AP-connected play (server DataStorage, in
// ap/session.ts — which reuses the model + helpers below). This module owns the data
// model, the solo store, and JSON export/import for offline cross-player analysis.

/** One recorded solve of a level. */
export interface SolveEvent {
  moves: number;
  pushes: number;
  timeMs: number; // wall-clock from attempt start to win
  ts: number; // epoch ms when solved
}

/** Raw per-level record. `visits` counts opens (a restart is the same visit); `sessions`
 * collects the distinct page-load session ids that visited, so uniqueVisits is derivable. */
export interface LevelStat {
  visits: number;
  sessions: string[];
  solves: SolveEvent[];
}

/** Rolled-up view for display (bests are the min over the solve log). */
export interface DerivedStat {
  visits: number;
  uniqueVisits: number;
  solveCount: number;
  bestMoves: number | null;
  bestPushes: number | null;
  bestTimeMs: number | null;
}

/** Microban number -> its record, for one corpus. */
export type CorpusStats = Record<number, LevelStat>;
/** corpus name -> its levels' stats. */
export type StatsStore = Record<string, CorpusStats>;

const STORAGE_KEY = "sokopelago.stats.v1";
export const STATS_SCHEMA = "sokopelago-stats/1";

/** A random id minted once per page load, so distinct play sessions can be counted. */
export const sessionId: string = makeSessionId();

function makeSessionId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    /* fall through */
  }
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

const VISITOR_KEY = "sokopelago.visitor.v1";

/** A stable id minted once and **persisted** across page loads (unlike `sessionId`, which is
 * per load). It anchors a unique-visitor count and a display-handle suffix without any account
 * or PII. Generated with the same crypto/fallback as `sessionId`. */
export const visitorId: string = loadVisitorId();

function loadVisitorId(): string {
  try {
    const existing = localStorage.getItem(VISITOR_KEY);
    if (existing) return existing;
  } catch {
    /* storage unavailable — fall through and mint an ephemeral id for this load */
  }
  const id = makeSessionId();
  try {
    localStorage.setItem(VISITOR_KEY, id);
  } catch {
    /* storage unavailable — the id is still usable for this page load */
  }
  return id;
}

export function emptyStat(): LevelStat {
  return { visits: 0, sessions: [], solves: [] };
}

/** Coerce an untrusted parsed value into a well-formed LevelStat (for load/import). */
export function normalizeStat(raw: unknown): LevelStat {
  const r = (raw ?? {}) as Partial<LevelStat>;
  const solves = Array.isArray(r.solves) ? r.solves : [];
  return {
    visits: typeof r.visits === "number" && r.visits >= 0 ? r.visits : 0,
    sessions: Array.isArray(r.sessions)
      ? r.sessions.filter((s): s is string => typeof s === "string")
      : [],
    solves: solves
      .filter((e): e is SolveEvent => Boolean(e) && typeof e === "object")
      .map((e) => ({
        moves: Number(e.moves) || 0,
        pushes: Number(e.pushes) || 0,
        timeMs: Number(e.timeMs) || 0,
        ts: Number(e.ts) || 0,
      })),
  };
}

/** Roll a raw record up into the display view. */
export function derive(stat: LevelStat | undefined): DerivedStat {
  if (!stat || (!stat.visits && !stat.solves.length)) {
    return {
      visits: stat?.visits ?? 0,
      uniqueVisits: 0,
      solveCount: 0,
      bestMoves: null,
      bestPushes: null,
      bestTimeMs: null,
    };
  }
  const best = (sel: (e: SolveEvent) => number): number | null =>
    stat.solves.length ? Math.min(...stat.solves.map(sel)) : null;
  return {
    visits: stat.visits,
    uniqueVisits: new Set(stat.sessions).size,
    solveCount: stat.solves.length,
    bestMoves: best((e) => e.moves),
    bestPushes: best((e) => e.pushes),
    bestTimeMs: best((e) => e.timeMs),
  };
}

/** Record a visit (one open) on a record, tagging the session once. Mutates + returns. */
export function addVisit(stat: LevelStat, sid: string): LevelStat {
  stat.visits += 1;
  if (!stat.sessions.includes(sid)) stat.sessions.push(sid);
  return stat;
}

/** Append a solve event. Mutates + returns. */
export function addSolve(stat: LevelStat, ev: SolveEvent): LevelStat {
  stat.solves.push(ev);
  return stat;
}

/** Merge `b` into `a`: summed visits, unioned sessions, concatenated solve log. */
export function mergeStat(a: LevelStat, b: LevelStat): LevelStat {
  a.visits += b.visits;
  for (const s of b.sessions) if (!a.sessions.includes(s)) a.sessions.push(s);
  a.solves.push(...b.solves);
  return a;
}

/** Shape of an export file (also what import accepts). */
export interface StatsExport {
  schema: string;
  player: string;
  exportedAt: number;
  corpora: StatsStore;
}

/** Serialize a store to the export object (flat + analysis-friendly across players). */
export function exportStore(store: StatsStore, player: string, exportedAt: number): StatsExport {
  return { schema: STATS_SCHEMA, player, exportedAt, corpora: store };
}

/** Merge an imported export into `store` in place. Returns false on a schema mismatch. */
export function importMerge(store: StatsStore, data: unknown): boolean {
  const d = data as Partial<StatsExport> | null;
  if (!d || d.schema !== STATS_SCHEMA || !d.corpora || typeof d.corpora !== "object") return false;
  for (const [corpus, levels] of Object.entries(d.corpora)) {
    const cs = (store[corpus] ??= {});
    for (const [n, raw] of Object.entries(levels ?? {})) {
      const k = Number(n);
      const incoming = normalizeStat(raw);
      cs[k] = cs[k] ? mergeStat(cs[k], incoming) : incoming;
    }
  }
  return true;
}

// --- Solo store (localStorage-backed) --------------------------------------

function loadStore(): StatsStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StatsStore;
    const store: StatsStore = {};
    for (const [corpus, levels] of Object.entries(parsed ?? {})) {
      const cs: CorpusStats = {};
      for (const [n, raw2] of Object.entries(levels ?? {})) cs[Number(n)] = normalizeStat(raw2);
      store[corpus] = cs;
    }
    return store;
  } catch {
    return {};
  }
}

function saveStore(store: StatsStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* storage unavailable — keep the in-memory store */
  }
}

/** Solo free-play statistics, persisted to localStorage. */
export class SoloStats {
  private store: StatsStore = loadStore();

  private corpus(c: string): CorpusStats {
    return (this.store[c] ??= {});
  }

  get(corpus: string, n: number): LevelStat | undefined {
    return this.store[corpus]?.[n];
  }

  derived(corpus: string, n: number): DerivedStat {
    return derive(this.get(corpus, n));
  }

  recordVisit(corpus: string, n: number): void {
    const cs = this.corpus(corpus);
    addVisit((cs[n] ??= emptyStat()), sessionId);
    saveStore(this.store);
  }

  recordSolve(corpus: string, n: number, ev: SolveEvent): void {
    const cs = this.corpus(corpus);
    addSolve((cs[n] ??= emptyStat()), ev);
    saveStore(this.store);
  }

  exportObject(player: string, exportedAt: number): StatsExport {
    return exportStore(this.store, player, exportedAt);
  }

  importObject(data: unknown): boolean {
    const ok = importMerge(this.store, data);
    if (ok) saveStore(this.store);
    return ok;
  }
}
