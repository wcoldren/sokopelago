// Play loop: fetch corpus -> parse -> model -> render -> input.
//
// Two modes share one board:
//   - Offline (default): play any of the 155 Microban levels locally, no server.
//   - AP-connected: the selector shows only the seed's levels, gated by received
//     world keys; solving a level reports a check; meeting the goal reports GOAL.

import { levelFromBoard } from "./engine/xsb";
import { Game } from "./engine/board";
import { Renderer } from "./engine/render";
import { attachInput } from "./engine/input";
import { effectiveDir, type Dir, type Level } from "./engine/types";
import { Session, loadPrefs, type SessionCallbacks } from "./ap/session";
import {
  SoloStats,
  derive,
  mergeStat,
  type DerivedStat,
  type SolveEvent,
  type StatsExport,
} from "./engine/stats";
import {
  levelsInWorld,
  nextLevelInWorldOrder,
  seedPositionInWorld,
  type SlotData,
} from "./ap/slotData";
import type { TrapVariant } from "./ap/ids";
import {
  parseSolution,
  planHint,
  animateSolutionPrefix,
  type AnimationHandle,
} from "./engine/solution";
import { fetchManifest } from "./engine/manifest";

const DEFAULT_CORPUS = "microban";

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
};

const canvas = $<HTMLCanvasElement>("board");
const levelGrid = $<HTMLDivElement>("level-grid");
const restartBtn = $<HTMLButtonElement>("restart-btn");
const undoBtn = $<HTMLButtonElement>("undo-btn");
const hintBtn = $<HTMLButtonElement>("hint-btn");
const skipBtn = $<HTMLButtonElement>("skip-btn");
const pullBtn = $<HTMLButtonElement>("pull-btn");
const statusEl = $<HTMLDivElement>("status");
const statsEl = $<HTMLDivElement>("stats");
const noticeEl = $<HTMLDivElement>("notice");
const hostInput = $<HTMLInputElement>("ap-host");
const slotInput = $<HTMLInputElement>("ap-slot");
const passInput = $<HTMLInputElement>("ap-pass");
const connectBtn = $<HTMLButtonElement>("ap-connect");
const connStatusEl = $<HTMLDivElement>("conn-status");
const goalLineEl = $<HTMLDivElement>("goal-line");
const statsExportBtn = $<HTMLButtonElement>("stats-export");
const statsImportBtn = $<HTMLButtonElement>("stats-import");
const statsImportFile = $<HTMLInputElement>("stats-import-file");
const statsStatusEl = $<HTMLSpanElement>("stats-status");

const renderer = new Renderer(canvas);

let levels: Level[] = [];
let solutions = new Map<number, string>(); // Microban number -> LURD solution string
// Par (optimal pushes) and normalized difficulty per Microban number, read from the
// bundled manifest so they work in BOTH solo free-play and AP-connected play (the seed's
// slot_data carries the same par for the apworld<->client check contract, but display is
// manifest-driven so it never depends on being connected).
let manifestPar = new Map<number, number>();
let manifestDifficulty = new Map<number, number>();
let loadedCorpus = DEFAULT_CORPUS; // which corpus manifest is currently loaded
let game: Game | null = null;
let current = 0;
let locked = false; // briefly true between solving and auto-advancing
let hintBoxMoves = 0; // box-moves (pushes/pulls) the Hint has revealed on the current level
let hintAnim: AnimationHandle | null = null; // in-flight hint playback (cancelled on level change)
let animating = false; // input blocked during a hint animation; never persists past it
let reversedControls = false; // set by a Reversed-Controls trap; cleared on level change
let pullMode = false; // when on, plain direction input pulls instead of pushing
let soloPullNoticed = false; // one-time "pull is a sandbox aid" heads-up shown in solo microban
let lastUnlockedCount = 0; // # of unlocked worlds last seen — detects a newly-opened world
let activeWorldTab: number | null = null; // AP mode: which world's tab is showing (null -> current)
const solvedOffline = new Set<number>(); // levels solved this session in free play (no session)
const solvedOptimalOffline = new Set<number>(); // of those, the ones solved in optimal (par) pushes

// Per-level play stats (visits + per-solve event log). Solo play persists to localStorage;
// AP play persists to the session's DataStorage. `attemptStart` clocks the current board
// for solve time; `attemptActive` guards against logging a "solve" more than once per fresh
// board (so nudging a box off and back onto a goal on a solved board doesn't re-log).
const soloStats = new SoloStats();
let attemptStart = Date.now();
let attemptActive = false;

const BIG_HINT_PUSHES = 3; // how many extra pushes a "big" hint (Shift+Hint) reveals/animates

let session: Session | null = null;
let slot: SlotData | null = null; // non-null once connected (AP mode)

const msg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/** Microban level number (1-based) for a parsed level (index is 0-based). */
const levelNumber = (lvl: Level): number => lvl.index + 1;

/** Push-par (optimal) for a level, from the bundled manifest — shown in solo and AP alike. */
const parTarget = (n: number): number | null => manifestPar.get(n) ?? null;

/** Efficient-tier push threshold, only when the connected seed has the efficiency tier on
 * (an AP reward concept); computed from the manifest par + the seed's margin. */
const effTarget = (n: number): number | null => {
  if (!slot?.par_checks || !slot?.efficiency_checks) return null;
  const par = manifestPar.get(n);
  if (par === undefined) return null;
  const margin = typeof slot.efficiency_margin === "number" ? slot.efficiency_margin : 0;
  return Math.floor(par * (1 + margin / 100));
};

/** Difficulty tier for a level ("easy"/"medium"/"hard"), or null if the manifest has no
 * score for it. Manifest-driven, so badges show in solo play too. The 0.33/0.66 cutoffs
 * mirror apworld/sokopelago/tiers.py (EASY_MAX/HARD_MIN) — keep the two in sync. */
function difficultyTier(n: number): "easy" | "medium" | "hard" | null {
  const d = manifestDifficulty.get(n);
  if (d === undefined) return null;
  return d >= 0.66 ? "hard" : d >= 0.33 ? "medium" : "easy";
}

/** Compact 3-pip difficulty badge (e.g. "◆◆◇"), or "" when no data is available. */
function difficultyBadge(n: number): string {
  const tier = difficultyTier(n);
  if (tier === null) return "";
  const filled = tier === "hard" ? 3 : tier === "medium" ? 2 : 1;
  return "◆".repeat(filled) + "◇".repeat(3 - filled);
}

function setStatus(text: string, win = false): void {
  statusEl.textContent = text;
  statusEl.classList.toggle("win", win);
}

/** The level title line shown in #status. In AP mode it's the seed-relative "World N · L{pos}"
 * (with the Microban corpus number as the detail); solo play shows the plain corpus level. */
function levelTitle(target: Level): string {
  const n = levelNumber(target);
  const badge = difficultyBadge(n);
  const tier = difficultyTier(n);
  const suffix = `${badge ? `  ${badge}` : ""}${tier ? `  ${tier}` : ""}`;
  if (slot && session) {
    const w = session.worldForLevel(n);
    const pos = seedPositionInWorld(slot, n);
    if (w !== undefined && pos > 0)
      return `World ${w} · L${pos} — Microban ${target.name}${suffix}`;
  }
  return `Level ${target.name}${suffix}`;
}

/** A single labeled metric chip (label + value). */
function chip(label: string, value: string, cls = ""): HTMLSpanElement {
  const el = document.createElement("span");
  el.className = cls ? `chip ${cls}` : "chip";
  const l = document.createElement("span");
  l.className = "label";
  l.textContent = label;
  el.append(l, document.createTextNode(value));
  return el;
}

/** Render the per-move metric chips (moves / pushes / par / eff) for the current level,
 * so the numbers are scannable instead of crammed into one status line. */
function renderStats(): void {
  statsEl.replaceChildren();
  if (!game) return;
  const n = levelNumber(game.level);
  const par = parTarget(n);
  const eff = effTarget(n);
  statsEl.append(chip("moves", String(game.moves)));
  const pushesText = par !== null ? `${game.pushes} / par ${par}` : String(game.pushes);
  const pushesCls = par !== null && game.pushes <= par ? "par-hit" : "";
  statsEl.append(chip("pushes", pushesText, pushesCls));
  if (eff !== null && par !== null && eff > par) {
    statsEl.append(chip("eff", `≤ ${eff}`));
  }
  statsEl.append(chip("time", formatMs(Date.now() - attemptStart)));
  // Lifetime play stats for this level (visits + bests over the solve log).
  const st = statsFor(n);
  if (st.visits > 0) {
    const uniq = st.uniqueVisits > 1 ? ` · ${st.uniqueVisits} sessions` : "";
    statsEl.append(chip("plays", `${st.visits}${uniq}`));
  }
  if (st.bestMoves !== null) {
    statsEl.append(
      chip("best", `${st.bestMoves}m / ${st.bestPushes}p / ${formatMs(st.bestTimeMs ?? 0)}`),
    );
  }
}

let noticeTimer: number | undefined;

/**
 * Show a lingering event notice (unlock, item received, solve, warning) on its own line,
 * so a subsequent move or auto-advance — which rewrite `#status` — don't wipe it. Stays
 * for `ms`, then fades. The live per-move state stays on `#status`.
 */
function notice(text: string, opts: { win?: boolean; ms?: number } = {}): void {
  const { win = false, ms = 5000 } = opts;
  noticeEl.textContent = text;
  noticeEl.classList.toggle("win", win);
  noticeEl.classList.remove("fading");
  if (noticeTimer !== undefined) window.clearTimeout(noticeTimer);
  noticeTimer = window.setTimeout(() => noticeEl.classList.add("fading"), ms);
}

function setConnStatus(text: string, kind?: "ok" | "err"): void {
  connStatusEl.textContent = text;
  connStatusEl.classList.toggle("ok", kind === "ok");
  connStatusEl.classList.toggle("err", kind === "err");
}

/** Human-readable win condition for the connected seed (shown on its own line).
 * `beat_final_region` is the supported goal (accurate sphere ordering — the final world needs all
 * keys); `solve_count` / `boss_level` are experimental. See docs/DESIGN-boss-zone.md. */
function goalDescription(s: SlotData): string {
  switch (s.goal) {
    case "solve_count":
      return `Goal: solve any ${s.goal_solve_count} of the ${s.level_count} levels.`;
    case "boss_level":
      return `Goal: solve the boss level — Microban ${s.goal_boss_level}.`;
    case "beat_final_region":
    default: {
      const k = levelsInWorld(s, s.final_world).length;
      const note = s.boss_all_keys ? " It opens only once you hold every world key." : "";
      return `Goal: solve every level in the final world (World ${s.final_world}${k ? ` — ${k} levels` : ""}).${note}`;
    }
  }
}

// --- Level selector --------------------------------------------------------

/** Levels shown in the selector: the whole corpus offline, the seed in AP mode. */
function shownLevels(): Level[] {
  if (!slot) return levels;
  return slot.levels.map((n) => levels[n - 1]).filter((l): l is Level => Boolean(l));
}

// Option markers — see the legend under the board: ★ optimal, ✦ efficient, ✓ solved, 🔒 locked, ◆ difficulty.

/** The efficiency margin (percent over optimal that still counts as ✦). Uses the seed's
 * margin when it ships the efficiency tier, else a default so the *visual* ✦ works even
 * when the seed has no par/efficiency reward checks. */
function effMarginPct(): number {
  return typeof slot?.efficiency_margin === "number" ? slot.efficiency_margin : 15;
}

/**
 * Performance marker for a level from the player's *best pushes* (the play-stats log) vs the
 * level's known optimal — so ★/✦ show in solo and multiworld alike, regardless of whether the
 * seed enabled par checks. Falls back to the AP par/efficiency check sets when no pushes were
 * recorded (e.g. a Skip clear), else null.
 */
function performanceMarker(n: number): "★" | "✦" | null {
  const par = parTarget(n);
  const best = statsFor(n).bestPushes;
  if (par !== null && best !== null) {
    if (best <= par) return "★";
    if (best <= Math.floor(par * (1 + effMarginPct() / 100))) return "✦";
    return null;
  }
  if (session?.isLevelPar(n)) return "★";
  if (session?.isLevelEfficient(n)) return "✦";
  return null;
}

/** Selector marker for a *solved* level: its performance tier, or a plain ✓. */
function solvedMarker(n: number): string {
  return performanceMarker(n) ?? "✓";
}

/** Solve-time performance note (manifest-par based) shown in both solo and AP. */
function performanceNote(n: number, pushes: number): string {
  const par = parTarget(n);
  if (par === null) return "";
  if (pushes <= par) return ` ★ optimal — ${par} pushes!`;
  const eff = Math.floor(par * (1 + effMarginPct() / 100));
  if (pushes <= eff)
    return ` ✦ efficient — ${pushes} pushes, ${pushes - par} over the optimal ${par}`;
  return ` (optimal ${par})`;
}

/** Difficulty-range pips for a world ("◆◇◇–◆◆◇", a single badge, or "" when unscored). */
function worldDifficulty(ns: number[]): string {
  const pips = (f: number): string => "◆".repeat(f) + "◇".repeat(3 - f);
  const fills = ns
    .map((n) => {
      const t = difficultyTier(n);
      return t === "hard" ? 3 : t === "medium" ? 2 : t === "easy" ? 1 : 0;
    })
    .filter((f) => f > 0);
  if (fills.length === 0) return "";
  const lo = Math.min(...fills);
  const hi = Math.max(...fills);
  return lo === hi ? pips(lo) : `${pips(lo)}–${pips(hi)}`;
}

/** A clickable level "pill": per-world number + state marker (★/✦/✓ solved, 🔒 gated). The
 * corpus number stays in the tooltip — it's the internal identity, not the player-facing label. */
function makePill(lvl: Level, posInWorld: number): HTMLButtonElement {
  const n = levelNumber(lvl);
  const btn = document.createElement("button");
  btn.className = "pill";
  btn.title = `Microban ${lvl.name}`;
  const solved = slot && session ? session.isLevelSolved(n) : solvedOffline.has(n);
  const playable = !slot || !session || session.isLevelPlayable(n);
  let mark = "";
  if (solved) {
    mark = solvedMarker(n);
    btn.classList.add("solved");
  } else if (slot && session && !playable) {
    mark = "🔒";
    btn.classList.add("locked");
    btn.disabled = true;
    if (session.needsPull(n) && !session.canPull) btn.title += " — needs the Pull ability";
  }
  const label = posInWorld > 0 ? String(posInWorld) : String(n);
  btn.textContent = mark ? `${mark} ${label}` : label;
  if (lvl.index === current) btn.classList.add("current");
  btn.addEventListener("click", () => loadLevel(lvl.index));
  return btn;
}

/** Append a world's header — name, difficulty range, and key/lock state — to `head`. The boss
 * world (all-keys gate) spells out "needs ALL keys (held/total)" so the gate isn't a mystery. */
function buildWorldHead(head: HTMLElement, w: number): void {
  const s = slot!;
  const isBoss = Boolean(s.boss_all_keys) && w === s.final_world;
  const name = document.createElement("span");
  name.className = "world-name";
  name.textContent = isBoss ? `Boss · World ${w}` : `World ${w}`;
  head.append(name);
  const diff = worldDifficulty(levelsInWorld(s, w));
  if (diff) {
    const d = document.createElement("span");
    d.className = "world-diff";
    d.textContent = diff;
    head.append(d);
  }
  const state = document.createElement("span");
  state.className = "world-state";
  if (session!.unlockedWorlds.has(w)) {
    state.textContent = w === 1 ? "open" : "key ✓";
    state.classList.add("open");
  } else if (isBoss) {
    state.textContent = `🔒 needs ALL keys (${session!.keysHeld}/${session!.keysTotal})`;
  } else {
    state.textContent = `🔒 needs World ${w} Key`;
  }
  head.append(state);
}

/** A world tab button: short label + lock/solved state; clicking switches the shown world. */
function makeWorldTab(w: number, levelsInW: Level[], active: boolean): HTMLButtonElement {
  const s = slot!;
  const isBoss = Boolean(s.boss_all_keys) && w === s.final_world;
  const tab = document.createElement("button");
  tab.className = "world-tab";
  tab.textContent = isBoss ? "Boss" : `W${w}`;
  if (active) tab.classList.add("active");
  if (!session!.unlockedWorlds.has(w)) {
    tab.classList.add("locked");
    tab.textContent += " 🔒";
  } else if (levelsInW.every((l) => session!.isLevelSolved(levelNumber(l)))) {
    tab.classList.add("solved");
  }
  tab.addEventListener("click", () => {
    activeWorldTab = w;
    rebuildLevelGrid();
  });
  return tab;
}

/** Rebuild the level picker: in AP mode a tab row of worlds with the *active* world's header +
 * pills shown (one world at a time); in solo free-play a single dropdown of the whole corpus. */
function rebuildLevelGrid(): void {
  levelGrid.replaceChildren();
  if (slot && session) {
    const worlds = Object.keys(slot.region_map)
      .map(Number)
      .sort((a, b) => a - b);
    const levelsOf = (w: number): Level[] =>
      levelsInWorld(slot!, w)
        .map((n) => levels[n - 1])
        .filter((l): l is Level => Boolean(l));
    // Show the explicitly-picked tab when still valid, else the current level's world, else first.
    const currentWorld = game ? session.worldForLevel(levelNumber(game.level)) : undefined;
    let active = activeWorldTab;
    if (active === null || !worlds.includes(active)) active = currentWorld ?? worlds[0];

    const tabs = document.createElement("div");
    tabs.className = "world-tabs";
    for (const w of worlds) tabs.append(makeWorldTab(w, levelsOf(w), w === active));
    levelGrid.append(tabs);

    if (active !== undefined) {
      const section = document.createElement("div");
      section.className = "world";
      const head = document.createElement("div");
      head.className = "world-head";
      buildWorldHead(head, active);
      section.append(head);
      const pills = document.createElement("div");
      pills.className = "pills";
      levelsOf(active).forEach((lvl, i) => pills.append(makePill(lvl, i + 1)));
      section.append(pills);
      levelGrid.append(section);
    }
  } else {
    // Solo free-play: the whole corpus is one flat list — a dropdown, not 155 buttons.
    const label = document.createElement("label");
    label.append(document.createTextNode("Level: "));
    const select = document.createElement("select");
    for (const lvl of shownLevels()) {
      const n = levelNumber(lvl);
      const opt = document.createElement("option");
      opt.value = String(lvl.index);
      const badge = difficultyBadge(n);
      const mark = solvedOffline.has(n) ? `  ${solvedMarker(n)}` : "";
      opt.textContent = `${lvl.name}${badge ? `  ${badge}` : ""}${mark}`;
      select.append(opt);
    }
    if (game) select.value = String(current);
    select.addEventListener("change", () => loadLevel(Number(select.value)));
    label.append(select);
    levelGrid.append(label);
  }
  updateValveButtons();
}

/** Next level to auto-advance to after solving `afterN`, in world-first order: the rest of the
 * current world, then forward worlds, then wrapping back (see nextLevelInWorldOrder). */
function nextPlayable(afterN: number): Level | null {
  if (!slot || !session) return null;
  const s = session;
  const n = nextLevelInWorldOrder(
    slot,
    afterN,
    (x) => s.isLevelSolved(x),
    (x) => s.isLevelPlayable(x),
  );
  return n === null ? null : (levels[n - 1] ?? null);
}

/**
 * Session state changed (item received, token consumed, etc.). Rebuild the selector, and
 * if a *new world just unlocked* while the player is parked on a solved level (the
 * dead-end case the freeze fix leaves interactive), pull them into the newly-open world so
 * they can keep going without hunting through the level grid.
 */
function onSessionUpdate(): void {
  rebuildLevelGrid();
  if (!slot || !session || !game) {
    lastUnlockedCount = session?.unlockedWorlds.size ?? 0;
    return;
  }
  const unlocked = session.unlockedWorlds.size;
  const newlyOpened = unlocked > lastUnlockedCount;
  lastUnlockedCount = unlocked;
  if (newlyOpened && !locked && !animating && session.isLevelSolved(levelNumber(game.level))) {
    const next = nextPlayable(levelNumber(game.level));
    if (next) {
      notice(`A new world is open — jumping to level ${levelNumber(next)}.`, { win: true });
      loadLevel(next.index);
    }
  }
}

// --- Play loop -------------------------------------------------------------

function loadLevel(i: number): void {
  const target = levels[i];
  if (!target) return;
  if (slot && session && !session.isLevelPlayable(levelNumber(target))) {
    const n = levelNumber(target);
    if (!session.isLevelUnlocked(n)) {
      notice(`Level ${n} is locked — needs the World ${session.worldForLevel(n)} Key.`);
    } else {
      notice(`Level ${n} needs the Pull ability — find it in the multiworld.`);
    }
    return;
  }
  hintAnim?.cancel(); // stop any in-flight hint playback from mutating the new board
  hintAnim = null;
  animating = false;
  current = i;
  // Keep the visible world tab on the level being played (so auto-advance follows along).
  if (slot && session)
    activeWorldTab = session.worldForLevel(levelNumber(target)) ?? activeWorldTab;
  game = new Game(target);
  beginAttempt();
  recordVisit(levelNumber(target));
  locked = false;
  hintBoxMoves = 0;
  reversedControls = false; // a trap's curse lasts only for the level it hit
  renderer.draw(game);
  setStatus(levelTitle(target));
  renderStats();
  rebuildLevelGrid(); // refresh the grid so the current level's pill is highlighted
}

function refreshStatus(): void {
  if (!game) return;
  renderStats();
  updateValveButtons();
}

/** Begin timing/counting a fresh attempt on the current board (a level load or restart). */
function beginAttempt(): void {
  attemptStart = Date.now();
  attemptActive = true;
}

/** Record one *visit* (an open) of level `n` against the active stats source. */
function recordVisit(n: number): void {
  if (slot && session) session.recordVisit(n);
  else soloStats.recordVisit(loadedCorpus, n);
}

/** Log a solve event for level `n` — once per fresh attempt (so re-winning a solved board
 * by nudging a box doesn't inflate the log). */
function recordSolveEvent(n: number): void {
  if (!game || !attemptActive) return;
  attemptActive = false;
  const ev: SolveEvent = {
    moves: game.moves,
    pushes: game.pushes,
    timeMs: Math.max(0, Date.now() - attemptStart),
    ts: Date.now(),
  };
  if (slot && session) session.recordSolve(n, ev);
  else soloStats.recordSolve(loadedCorpus, n, ev);
}

/** Rolled-up stats (visits / unique / bests) for level `n` from the active source. */
function statsFor(n: number): DerivedStat {
  return derive(slot && session ? session.statFor(n) : soloStats.get(loadedCorpus, n));
}

/** Compact mm:ss / ss formatting for a millisecond duration. */
function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
}

function setStatsStatus(text: string): void {
  statsStatusEl.textContent = text;
}

/** Build a portable stats export: the solo store, plus the live AP-session stats (current
 * corpus) when connected. Deep-cloned so merging never mutates the live stores. */
function buildStatsExport(): StatsExport {
  const player = slotInput.value.trim() || "player";
  const obj = structuredClone(soloStats.exportObject(player, Date.now()));
  if (slot && session) {
    const cs = (obj.corpora[loadedCorpus] ??= {});
    for (const [k, stat] of Object.entries(session.statsRecord())) {
      const n = Number(k);
      const clone = structuredClone(stat);
      cs[n] = cs[n] ? mergeStat(cs[n], clone) : clone;
    }
  }
  return obj;
}

/** Trigger a client-side file download of `text`. */
function download(filename: string, text: string): void {
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportStats(): void {
  const obj = buildStatsExport();
  download(`sokopelago-stats-${obj.exportedAt}.json`, JSON.stringify(obj, null, 2));
  setStatsStatus("Exported your play stats.");
}

async function importStats(file: File): Promise<void> {
  try {
    const data: unknown = JSON.parse(await file.text());
    const ok = soloStats.importObject(data);
    setStatsStatus(
      ok ? "Imported and merged stats into local play." : "Not a Sokopelago stats file.",
    );
    if (ok) refreshStatus();
  } catch {
    setStatsStatus("Couldn't read that file.");
  }
}

/** Whether level `n` is already marked solved (AP session, or this session's free play). */
function alreadySolved(n: number): boolean {
  return slot && session ? session.isLevelSolved(n) : solvedOffline.has(n);
}

function onSolved(): void {
  if (!game) return;
  const lvl = game.level;
  const solved = lvl.name;
  const n = levelNumber(lvl);
  recordSolveEvent(n);

  if (slot && session) {
    session.reportSolved(n, game.pushes);
    rebuildLevelGrid(); // mark the just-solved level's pill
    // Performance feedback is manifest-par based, so ★/✦ show even when the seed has no par
    // checks. (The AP par/efficiency reward checks, if on, were just sent by reportSolved.)
    const parNote = performanceNote(n, game.pushes);
    const next = nextPlayable(n);
    notice(
      next
        ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes)${parNote} → next…`
        : `Solved ${solved}! (${game.pushes} pushes)${parNote} No more playable levels right now — open a world (or wait for a key) and you can keep going.`,
      { win: true },
    );
    // Only hold the board locked during the brief auto-advance beat. With no next level,
    // leave it interactive so the player isn't trapped on a solved board (a later World
    // Key, the selector, or Restart all still work).
    if (next) {
      locked = true;
      window.setTimeout(() => loadLevel(next.index), 1100);
    } else {
      locked = false;
    }
    return;
  }

  solvedOffline.add(n);
  const par = parTarget(n);
  if (par !== null && game.pushes <= par) solvedOptimalOffline.add(n);
  rebuildLevelGrid(); // reflect ✓/★/✦ on the pills for solo play
  const parNote = performanceNote(n, game.pushes);
  const hasNext = current < levels.length - 1;
  notice(
    hasNext
      ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes)${parNote} → next…`
      : `Solved ${solved}!${parNote} That's the last level. 🎉`,
    { win: true },
  );
  if (hasNext) {
    locked = true;
    window.setTimeout(() => loadLevel(current + 1), 1100);
  } else {
    locked = false;
  }
}

/**
 * A board win just happened. Route it: a first solve runs the full solve flow
 * (check + notice + auto-advance); a win on an *already-solved* level (a replay) only
 * attempts a tier upgrade — never re-advancing or re-locking, so nudging a box off and
 * back onto a goal on a dead-end board can't re-spam notices.
 */
function handleWin(): void {
  if (!game || !game.isWin()) {
    refreshStatus();
    return;
  }
  const n = levelNumber(game.level);
  if (!alreadySolved(n)) onSolved();
  else maybeUpgradeSolve(n);
}

/**
 * Replay of an already-cleared level: if the player beat their recorded tier, send the
 * par/efficiency check they newly earned and announce the upgrade. `reportSolved` is
 * idempotent and only fires a tier check it hasn't fired yet, so this is safe to call
 * on every replay win. Never advances or locks the board.
 */
function maybeUpgradeSolve(n: number): void {
  if (!game) return;
  recordSolveEvent(n); // a replay that wins is still a solve worth logging (better time, etc.)
  if (slot && session) {
    // Already at the top tier (or the seed has no par checks) → nothing to earn.
    if (slot.par_checks && !session.isLevelPar(n)) {
      const wasEfficient = session.isLevelEfficient(n);
      session.reportSolved(n, game.pushes);
      const par = parTarget(n);
      if (session.isLevelPar(n)) {
        rebuildLevelGrid();
        notice(`★ Upgraded ${game.level.name} to perfect — optimal ${par} pushes!`, { win: true });
      } else if (session.isLevelEfficient(n) && !wasEfficient) {
        rebuildLevelGrid();
        notice(`✦ Upgraded ${game.level.name} to efficient (≤${effTarget(n)}, par ${par})!`, {
          win: true,
        });
      }
    }
    refreshStatus();
    return;
  }
  // Solo free-play: upgrade ✓ → ★ when this replay was optimal.
  const par = parTarget(n);
  if (par !== null && game.pushes <= par && !solvedOptimalOffline.has(n)) {
    solvedOptimalOffline.add(n);
    rebuildLevelGrid();
    notice(`★ Upgraded ${game.level.name} to optimal (${par} pushes)!`, { win: true });
  }
  refreshStatus();
}

/** Whether Pull is part of this context at all: always in solo (god-mode for dev/testing);
 * in AP only on a pull-capable corpus or a pull-logic seed. */
function pullInSeed(): boolean {
  if (!session) return true;
  return loadedCorpus !== DEFAULT_CORPUS || Boolean(slot?.pull_logic);
}

/** Whether the pull mechanic is usable right now: always in solo; in an AP seed only when
 * Pull is part of it AND not still gated behind the (unreceived) Pull ability. */
function canPullNow(): boolean {
  if (!session) return true;
  return pullInSeed() && session.canPull;
}

function move(dir: Dir): void {
  if (!game || locked || animating) return;
  if (pullMode) {
    pull(dir);
    return;
  }
  if (!game.move(effectiveDir(dir, reversedControls))) return;
  renderer.draw(game);
  handleWin();
}

/** Pull a box that's directly behind the player (the expert mechanic). */
function pull(dir: Dir): void {
  if (!game || locked || animating) return;
  if (!canPullNow()) {
    notice(
      pullInSeed()
        ? "The Pull ability is needed here — find it in the multiworld."
        : "Pull isn't used in this seed.",
    );
    return;
  }
  if (!game.pull(effectiveDir(dir, reversedControls))) return;
  // Solo free-play on the push-only Microban corpus: Pull is a hidden keyboard aid (the button
  // stays hidden). Flag once that these levels don't need it, so a pulled clear isn't mistaken
  // for the intended solve. (A pull corpus loaded solo genuinely uses pull — no note there.)
  if (!session && loadedCorpus === DEFAULT_CORPUS && !soloPullNoticed) {
    soloPullNoticed = true;
    notice("Pull here is a free sandbox aid — these Microban levels all solve with pushes alone.", {
      ms: 7000,
    });
  }
  renderer.draw(game);
  handleWin();
}

function restart(): void {
  if (!game) return;
  hintAnim?.cancel(); // a manual restart cancels any hint playback
  hintAnim = null;
  animating = false;
  game.restart();
  beginAttempt(); // same visit, fresh attempt — re-clock for solve time
  locked = false;
  renderer.draw(game);
  refreshStatus();
}

// --- Escape valves (AP mode) -----------------------------------------------

/** Undo the last move. Free offline; consumes an Undo Charge when connected. */
function undo(): void {
  if (!game || locked || animating || !game.canUndo()) return;
  // Smart undo: if there's a push/pull in the history, this undo "takes back the last
  // push" — rewinding the trailing walk steps and that one box-move (one Undo Charge).
  // With only walk moves so far, step back a single walk for free.
  if (game.hasBoxMove()) {
    if (slot && session && !session.useUndo()) {
      notice("No Undo Charges available.");
      return;
    }
    let step: ReturnType<Game["undoStep"]>;
    do {
      step = game.undoStep();
    } while (step === "walk"); // stop once the last box-move is reverted
  } else {
    game.undoStep(); // pure-walk history → free single step back
  }
  renderer.draw(game);
  refreshStatus();
}

/** Small hint: reveal the next push (the Hint button / H). The first push is free. */
function useHint(): void {
  runHint(1);
}

/** Big hint: reveal several more pushes at once (Shift+Hint / Shift+H), costing more tokens. */
function useBigHint(): void {
  runHint(BIG_HINT_PUSHES);
}

/**
 * Reveal `addPushes` more box-moves (pushes/pulls) by restarting the board and *animating*
 * the optimal line from the start, up to that push. The first push is free; each push beyond
 * it costs one Hint Token when connected (free in solo). Never plays the final winning push —
 * the player finishes it themselves.
 */
function runHint(addPushes: number): void {
  if (!game || locked || animating) return;
  const n = levelNumber(game.level);
  const solution = solutions.get(n);
  if (!solution) {
    notice("No hint is available for this level.");
    return;
  }
  const moves = parseSolution(solution);
  const plan = planHint(hintBoxMoves, addPushes, moves);
  if (plan.atEnd) {
    notice("Hint: you're at the final push — finish it yourself! 🙂");
    return;
  }
  if (slot && session && plan.cost > 0) {
    if (session.available.hint < plan.cost) {
      notice(`Not enough Hint Tokens — need ${plan.cost}, have ${session.available.hint}.`);
      return;
    }
    for (let i = 0; i < plan.cost; i++) session.useHint();
  }
  hintBoxMoves = plan.boxMoves;
  const shown = plan.boxMoves; // pushes revealed (0 = the free walk-up on a single-push level)
  animating = true;
  updateValveButtons(); // reflect the spent tokens + disable controls during playback
  const g = game;
  hintAnim = animateSolutionPrefix(g, moves, plan.moveCount, {
    onStep: () => {
      renderer.draw(g);
      setStatus(
        shown > 0 ? `Hint: showing the first ${shown} push(es)…` : "Hint: walk to the box…",
      );
    },
    onDone: () => {
      animating = false;
      hintAnim = null;
      setStatus(
        shown > 0
          ? `Hint: showing the first ${shown} push(es). Your move!`
          : "Hint: there's the box — your move!",
      );
      updateValveButtons();
    },
  });
}

/** Consume a Skip Token to clear the current level (sends its check), then advance. */
function useSkip(): void {
  if (!game || animating || !slot || !session) return;
  const n = levelNumber(game.level);
  if (!session.useSkip(n)) {
    notice("No Skip Tokens available (or already solved).");
    return;
  }
  locked = true;
  notice(`Skipped level ${n} — check sent.`, { win: true });
  rebuildLevelGrid();
  const next = nextPlayable(n);
  if (next) window.setTimeout(() => loadLevel(next.index), 900);
}

/** Apply a (presentation-only) trap effect — never alters the solvable board. */
function triggerTrap(variant: TrapVariant): void {
  if (variant === "reversed") {
    reversedControls = true;
    notice("⚡ Trap: Reversed Controls — until you change levels!");
    return;
  }
  const cls = variant === "scramble" ? "trap-scramble" : "trap-decoy";
  canvas.classList.add(cls);
  window.setTimeout(() => canvas.classList.remove(cls), 1500);
  notice(variant === "scramble" ? "⚡ Trap: Scramble!" : "⚡ Trap: Decoy Box!");
}

/** Toggle sticky pull mode (plain arrows pull). Shift+arrow always pulls regardless. */
function togglePull(): void {
  if (!canPullNow()) {
    notice("The Pull ability is needed here — find it in the multiworld.");
    return;
  }
  pullMode = !pullMode;
  notice(pullMode ? "Pull mode ON — arrows pull (Shift+arrow always pulls)." : "Pull mode off.");
  updateValveButtons();
}

/** Sync the valve buttons' labels/counts and enabled state with the session. */
function updateValveButtons(): void {
  const ap = Boolean(slot && session);
  hintBtn.hidden = false; // Hint is free in solo play (like Undo); token-gated when connected
  skipBtn.hidden = !ap;

  // Show the Pull button only when the loaded corpus/seed actually uses pull (so it stays
  // out of the way in plain solo Microban). The keyboard god-mode (canPullNow) is separate.
  const pullRelevant = loadedCorpus !== DEFAULT_CORPUS || Boolean(slot?.pull_logic);
  pullBtn.hidden = !pullRelevant;
  if (pullRelevant) {
    const usable = canPullNow();
    if (!usable) pullMode = false;
    pullBtn.disabled = !usable || locked || animating;
    pullBtn.textContent = usable ? `Pull: ${pullMode ? "on" : "off"}` : "Pull (find it)";
  }

  const busy = locked || animating;
  const canUndo = Boolean(game?.canUndo()) && !busy;
  const hasHint = Boolean(game && solutions.has(levelNumber(game.level)));
  if (ap && session) {
    const a = session.available;
    undoBtn.textContent = `Undo (${a.undo})`;
    undoBtn.disabled = !canUndo || a.undo <= 0;
    hintBtn.textContent = `Hint (${a.hint})`;
    hintBtn.disabled = a.hint <= 0 || busy || !hasHint;
    skipBtn.textContent = `Skip (${a.skip})`;
    skipBtn.disabled =
      a.skip <= 0 || busy || (game ? session.isLevelSolved(levelNumber(game.level)) : true);
  } else {
    undoBtn.textContent = "Undo";
    undoBtn.disabled = !canUndo;
    hintBtn.textContent = "Hint";
    hintBtn.disabled = busy || !hasHint;
  }
}

// --- AP connection ---------------------------------------------------------

function handleDisconnect(): void {
  session = null;
  slot = null;
  pullMode = false;
  lastUnlockedCount = 0;
  connectBtn.textContent = "Connect";
  connectBtn.disabled = false;
  setConnStatus("Disconnected — free play (all levels).");
  goalLineEl.textContent = "";
  void reloadDefaultCorpus();
}

/** Back to the default corpus for offline free play after a disconnect. */
async function reloadDefaultCorpus(): Promise<void> {
  if (loadedCorpus !== DEFAULT_CORPUS) {
    try {
      await loadCorpus(DEFAULT_CORPUS);
    } catch {
      /* keep whatever is loaded */
    }
  }
  rebuildLevelGrid();
  loadLevel(0);
}

/** After auth, load the seed's corpus (if different) then show its first playable level. */
async function onConnectedReady(s: SlotData): Promise<void> {
  if (s.corpus && s.corpus !== loadedCorpus) {
    try {
      await loadCorpus(s.corpus);
    } catch (e) {
      setConnStatus(`Connected, but couldn't load corpus "${s.corpus}": ${msg(e)}`, "err");
    }
  }
  lastUnlockedCount = session?.unlockedWorlds.size ?? 0; // baseline so connect doesn't auto-jump
  activeWorldTab = null; // fresh connection: default the tab to the current/first world
  rebuildLevelGrid();
  const first = nextPlayable(0);
  if (first) loadLevel(first.index);
}

async function connect(): Promise<void> {
  const host = hostInput.value.trim();
  const slotName = slotInput.value.trim();
  if (!host || !slotName) {
    setConnStatus("Enter a host and slot name to connect.", "err");
    return;
  }

  connectBtn.disabled = true;
  setConnStatus(`Connecting to ${host}…`);

  const callbacks: SessionCallbacks = {
    onConnected: (s) => {
      slot = s;
      connectBtn.textContent = "Disconnect";
      connectBtn.disabled = false;
      setConnStatus(`Connected as ${s.player_name} — ${s.level_count} levels.`, "ok");
      goalLineEl.textContent = goalDescription(s);
      void onConnectedReady(s);
    },
    onUpdate: onSessionUpdate,
    onGoal: () => setConnStatus(`Goal complete! 🏆 (${slot?.goal})`, "ok"),
    onMessage: (text) => notice(text),
    onTrap: (variant) => triggerTrap(variant),
    onDisconnect: () => handleDisconnect(),
  };

  session = new Session(callbacks);
  try {
    await session.connect(host, slotName, passInput.value);
  } catch (err) {
    session = null;
    connectBtn.disabled = false;
    setConnStatus(`Connection failed: ${msg(err)}`, "err");
  }
}

function onConnectClick(): void {
  if (session && session.authenticated) {
    session.disconnect(); // fires onDisconnect -> handleDisconnect
  } else {
    void connect();
  }
}

// --- Bootstrap -------------------------------------------------------------

/** Fetch a corpus manifest by name: boards (rendered) + solutions (hints). */
async function loadCorpus(corpus: string): Promise<void> {
  const entries = await fetchManifest(corpus);
  levels = entries.map((e) => levelFromBoard(e.board, e.n - 1, e.name));
  solutions = new Map(entries.filter((e) => e.solution).map((e) => [e.n, e.solution as string]));
  manifestPar = new Map(
    entries.filter((e) => typeof e.par === "number").map((e) => [e.n, e.par as number]),
  );
  manifestDifficulty = new Map(
    entries
      .filter((e) => typeof e.difficulty === "number")
      .map((e) => [e.n, e.difficulty as number]),
  );
  loadedCorpus = corpus;
}

async function main(): Promise<void> {
  setStatus("Loading levels…");
  await loadCorpus(DEFAULT_CORPUS);

  const prefs = loadPrefs();
  if (prefs) {
    hostInput.value = prefs.host;
    slotInput.value = prefs.slot;
  }

  rebuildLevelGrid();
  restartBtn.addEventListener("click", restart);
  undoBtn.addEventListener("click", undo);
  // Shift-click (or Shift+H) is a bigger hint: more moves animated for more tokens.
  hintBtn.addEventListener("click", (e) => runHint(e.shiftKey ? BIG_HINT_PUSHES : 1));
  skipBtn.addEventListener("click", useSkip);
  pullBtn.addEventListener("click", togglePull);
  connectBtn.addEventListener("click", onConnectClick);
  statsExportBtn.addEventListener("click", exportStats);
  statsImportBtn.addEventListener("click", () => statsImportFile.click());
  statsImportFile.addEventListener("change", () => {
    const file = statsImportFile.files?.[0];
    if (file) void importStats(file);
    statsImportFile.value = ""; // allow re-importing the same file
  });
  attachInput({
    onMove: move,
    onRestart: restart,
    onUndo: undo,
    onHint: useHint,
    onBigHint: useBigHint,
    onSkip: useSkip,
    onPull: pull,
  });

  loadLevel(0);
}

main().catch((err) => {
  console.error(err);
  setStatus(`Error: ${msg(err)}`);
});
