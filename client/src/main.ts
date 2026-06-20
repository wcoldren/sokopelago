// Play loop: fetch corpus -> parse -> model -> render -> input.
//
// Two modes share one board:
//   - Offline (default): play any of the 155 Microban levels locally, no server.
//   - AP-connected: the selector shows only the seed's levels, gated by received
//     world keys; solving a level reports a check; meeting the goal reports GOAL.

import { levelFromBoard } from "./xsb";
import { Game } from "./board";
import { Renderer } from "./render";
import { attachInput } from "./input";
import { effectiveDir, type Dir, type Level } from "./types";
import { Session, loadPrefs, type SessionCallbacks } from "./ap/session";
import type { SlotData } from "./ap/slotData";
import type { TrapVariant } from "./ap/ids";
import { parseSolution, planHint, animateSolutionPrefix, type AnimationHandle } from "./solution";

const DEFAULT_CORPUS = "microban";
// Base-relative so the fetch resolves under whatever path the site is served from
// (root locally, /sokopelago/ on GitHub Pages). BASE_URL is the Vite `base` ("./").
const manifestUrl = (corpus: string): string => `${import.meta.env.BASE_URL}data/${corpus}.json`;

/** One level entry in a bundled corpus manifest (data/<corpus>.json). */
interface ManifestEntry {
  n: number;
  name: string;
  board: string[];
  solution?: string;
  par?: number;
  difficulty?: number;
}

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
};

const canvas = $<HTMLCanvasElement>("board");
const select = $<HTMLSelectElement>("level-select");
const restartBtn = $<HTMLButtonElement>("restart-btn");
const undoBtn = $<HTMLButtonElement>("undo-btn");
const hintBtn = $<HTMLButtonElement>("hint-btn");
const skipBtn = $<HTMLButtonElement>("skip-btn");
const pullBtn = $<HTMLButtonElement>("pull-btn");
const statusEl = $<HTMLDivElement>("status");
const noticeEl = $<HTMLDivElement>("notice");
const hostInput = $<HTMLInputElement>("ap-host");
const slotInput = $<HTMLInputElement>("ap-slot");
const passInput = $<HTMLInputElement>("ap-pass");
const connectBtn = $<HTMLButtonElement>("ap-connect");
const connStatusEl = $<HTMLDivElement>("conn-status");

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
let lastUnlockedCount = 0; // # of unlocked worlds last seen — detects a newly-opened world
const solvedOffline = new Set<number>(); // levels solved this session in free play (no session)

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
 * score for it. Manifest-driven, so badges show in solo play too. */
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

// --- Level selector --------------------------------------------------------

/** Levels shown in the selector: the whole corpus offline, the seed in AP mode. */
function shownLevels(): Level[] {
  if (!slot) return levels;
  return slot.levels.map((n) => levels[n - 1]).filter((l): l is Level => Boolean(l));
}

// Option markers — see the legend under the board: ★ par, ✦ efficient, ✓ solved, 🔒 locked, ◆ difficulty.
function solvedMarker(n: number): string {
  if (!session) return "✓";
  if (session.isLevelPar(n)) return "★"; // perfect (exactly optimal)
  if (session.isLevelEfficient(n)) return "✦"; // within the efficiency margin
  return "✓";
}

function optionLabel(lvl: Level): string {
  const n = levelNumber(lvl);
  const badge = difficultyBadge(n);
  const base = `${n}. ${lvl.name}${badge ? `  ${badge}` : ""}`;
  if (!slot || !session) {
    // Solo free-play: still reflect levels solved this session.
    return solvedOffline.has(n) ? `✓ ${base}` : base;
  }
  if (session.isLevelSolved(n)) return `${solvedMarker(n)} ${base}`;
  // The world's lock state is shown by the <optgroup> label, so options just flag the gate.
  if (!session.isLevelUnlocked(n)) return `🔒 ${base}`;
  if (session.needsPull(n) && !session.canPull) return `🔒 ${base} (needs Pull)`;
  return base;
}

function makeOption(lvl: Level): HTMLOptionElement {
  const opt = document.createElement("option");
  opt.value = String(lvl.index);
  opt.textContent = optionLabel(lvl);
  if (slot && session && !session.isLevelPlayable(levelNumber(lvl))) opt.disabled = true;
  return opt;
}

function rebuildSelector(): void {
  select.innerHTML = "";
  const shown = shownLevels();
  if (slot && session) {
    // Group levels by world so the key/world structure is obvious at a glance.
    const byWorld = new Map<number, Level[]>();
    for (const lvl of shown) {
      const w = session.worldForLevel(levelNumber(lvl)) ?? 0;
      const arr = byWorld.get(w);
      if (arr) arr.push(lvl);
      else byWorld.set(w, [lvl]);
    }
    for (const w of [...byWorld.keys()].sort((a, b) => a - b)) {
      const group = document.createElement("optgroup");
      const open = session.unlockedWorlds.has(w);
      group.label = `World ${w}${open ? "" : " — 🔒 key needed"}`;
      for (const lvl of byWorld.get(w)!) group.appendChild(makeOption(lvl));
      select.appendChild(group);
    }
  } else {
    for (const lvl of shown) select.appendChild(makeOption(lvl));
  }
  if (game) select.value = String(current);
  updateValveButtons();
}

/** Next unlocked, unsolved seed level — preferring ones after `afterN`. */
function nextPlayable(afterN: number): Level | null {
  if (!slot || !session) return null;
  const playable = shownLevels().filter(
    (l) => session!.isLevelPlayable(levelNumber(l)) && !session!.isLevelSolved(levelNumber(l)),
  );
  if (playable.length === 0) return null;
  return playable.find((l) => levelNumber(l) > afterN) ?? playable[0];
}

/**
 * Session state changed (item received, token consumed, etc.). Rebuild the selector, and
 * if a *new world just unlocked* while the player is parked on a solved level (the
 * dead-end case the freeze fix leaves interactive), pull them into the newly-open world so
 * they can keep going without hunting through the dropdown.
 */
function onSessionUpdate(): void {
  rebuildSelector();
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
    select.value = String(current);
    return;
  }
  hintAnim?.cancel(); // stop any in-flight hint playback from mutating the new board
  hintAnim = null;
  animating = false;
  current = i;
  select.value = String(current);
  game = new Game(target);
  locked = false;
  hintBoxMoves = 0;
  reversedControls = false; // a trap's curse lasts only for the level it hit
  renderer.draw(game);
  const par = parTarget(levelNumber(target));
  const eff = effTarget(levelNumber(target));
  const parSuffix =
    par !== null ? ` — par ${par} pushes${eff !== null && eff > par ? ` (eff ≤${eff})` : ""}` : "";
  const tier = difficultyTier(levelNumber(target));
  const diffSuffix = tier ? ` — ${tier}` : "";
  setStatus(`Level ${game.level.name} — ${game.boxes.length} boxes${parSuffix}${diffSuffix}`);
  updateValveButtons();
}

function refreshStatus(): void {
  if (!game) return;
  const par = parTarget(levelNumber(game.level));
  const eff = effTarget(levelNumber(game.level));
  const parSuffix =
    par !== null ? ` / par ${par}${eff !== null && eff > par ? ` (eff ≤${eff})` : ""}` : "";
  setStatus(`Level ${game.level.name} — moves ${game.moves}, pushes ${game.pushes}${parSuffix}`);
  updateValveButtons();
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

  if (slot && session) {
    session.reportSolved(n, game.pushes);
    rebuildSelector(); // mark the just-solved option
    const par = parTarget(n);
    const eff = effTarget(n);
    let parNote = "";
    if (slot.par_checks && par !== null) {
      if (session.isLevelPar(n)) {
        parNote = ` ★ perfect — optimal ${par} pushes!`;
      } else if (session.isLevelEfficient(n)) {
        parNote = ` ✦ efficient (≤${eff}, par ${par})!`;
      } else {
        parNote =
          eff !== null && eff > par
            ? ` (par ${par} / eff ≤${eff} — missed)`
            : ` (par ${par} — par check missed)`;
      }
    }
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
  rebuildSelector(); // reflect the ✓ in the dropdown for solo play
  const par = parTarget(n);
  const parNote =
    par !== null ? (game.pushes <= par ? ` ★ optimal (${par} pushes)!` : ` (par ${par})`) : "";
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
  // Don't re-fire the solve flow if this level is already solved (e.g. nudging a box off
  // and back onto a goal on a dead-end board) — that would re-spam notices / re-lock.
  if (game.isWin() && !alreadySolved(levelNumber(game.level))) onSolved();
  else refreshStatus();
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
  renderer.draw(game);
  if (game.isWin() && !alreadySolved(levelNumber(game.level))) onSolved();
  else refreshStatus();
}

function restart(): void {
  if (!game) return;
  hintAnim?.cancel(); // a manual restart cancels any hint playback
  hintAnim = null;
  animating = false;
  game.restart();
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
  rebuildSelector();
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
  rebuildSelector();
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
  rebuildSelector();
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
      setConnStatus(
        `Connected as ${s.player_name} — ${s.level_count} levels, goal: ${s.goal}.`,
        "ok",
      );
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
  const url = manifestUrl(corpus);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`failed to load ${url}: ${res.status}`);
  const entries = (await res.json()) as ManifestEntry[];
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

  rebuildSelector();
  select.addEventListener("change", () => loadLevel(Number(select.value)));
  restartBtn.addEventListener("click", restart);
  undoBtn.addEventListener("click", undo);
  // Shift-click (or Shift+H) is a bigger hint: more moves animated for more tokens.
  hintBtn.addEventListener("click", (e) => runHint(e.shiftKey ? BIG_HINT_PUSHES : 1));
  skipBtn.addEventListener("click", useSkip);
  pullBtn.addEventListener("click", togglePull);
  connectBtn.addEventListener("click", onConnectClick);
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
