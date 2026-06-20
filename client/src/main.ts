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
import { parForLevel, difficultyForLevel, type SlotData } from "./ap/slotData";
import type { TrapVariant } from "./ap/ids";
import { parseSolution, replaySolutionPrefix } from "./solution";

const MANIFEST_URL = "/data/microban.json";

/** One level entry in the bundled manifest (data/microban.json). */
interface ManifestEntry {
  n: number;
  name: string;
  board: string[];
  solution?: string;
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
const statusEl = $<HTMLDivElement>("status");
const hostInput = $<HTMLInputElement>("ap-host");
const slotInput = $<HTMLInputElement>("ap-slot");
const passInput = $<HTMLInputElement>("ap-pass");
const connectBtn = $<HTMLButtonElement>("ap-connect");
const connStatusEl = $<HTMLDivElement>("conn-status");

const renderer = new Renderer(canvas);

let levels: Level[] = [];
let solutions = new Map<number, string>(); // Microban number -> LURD solution string
let game: Game | null = null;
let current = 0;
let locked = false; // briefly true between solving and auto-advancing
let hintIndex = 0; // solution moves revealed on the current level
let reversedControls = false; // set by a Reversed-Controls trap; cleared on level change

let session: Session | null = null;
let slot: SlotData | null = null; // non-null once connected (AP mode)

const msg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/** Microban level number (1-based) for a parsed level (index is 0-based). */
const levelNumber = (lvl: Level): number => lvl.index + 1;

/** Push-par for a level when the connected seed has Par Checks on, else null. */
const parTarget = (n: number): number | null => (slot?.par_checks ? parForLevel(slot, n) : null);

/** Difficulty tier for a level ("easy"/"medium"/"hard"), or null if no data (offline). */
function difficultyTier(n: number): "easy" | "medium" | "hard" | null {
  const d = slot ? difficultyForLevel(slot, n) : null;
  if (d === null) return null;
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

function optionLabel(lvl: Level): string {
  const n = levelNumber(lvl);
  const badge = difficultyBadge(n);
  const base = `${n}. ${lvl.name}${badge ? `  ${badge}` : ""}`;
  if (!slot || !session) return base;
  if (session.isLevelSolved(n)) return `${session.isLevelPar(n) ? "★" : "✓"} ${base}`;
  if (!session.isLevelUnlocked(n)) {
    return `🔒 ${base} — World ${session.worldForLevel(n)} (locked)`;
  }
  return base;
}

function rebuildSelector(): void {
  select.innerHTML = "";
  for (const lvl of shownLevels()) {
    const opt = document.createElement("option");
    opt.value = String(lvl.index);
    opt.textContent = optionLabel(lvl);
    if (slot && session && !session.isLevelUnlocked(levelNumber(lvl))) {
      opt.disabled = true;
    }
    select.appendChild(opt);
  }
  if (game) select.value = String(current);
  updateValveButtons();
}

/** Next unlocked, unsolved seed level — preferring ones after `afterN`. */
function nextPlayable(afterN: number): Level | null {
  if (!slot || !session) return null;
  const playable = shownLevels().filter(
    (l) => session!.isLevelUnlocked(levelNumber(l)) && !session!.isLevelSolved(levelNumber(l)),
  );
  if (playable.length === 0) return null;
  return playable.find((l) => levelNumber(l) > afterN) ?? playable[0];
}

// --- Play loop -------------------------------------------------------------

function loadLevel(i: number): void {
  const target = levels[i];
  if (!target) return;
  if (slot && session && !session.isLevelUnlocked(levelNumber(target))) {
    setStatus(
      `Level ${levelNumber(target)} is locked — needs the World ${session.worldForLevel(
        levelNumber(target),
      )} Key.`,
    );
    select.value = String(current);
    return;
  }
  current = i;
  select.value = String(current);
  game = new Game(target);
  locked = false;
  hintIndex = 0;
  reversedControls = false; // a trap's curse lasts only for the level it hit
  renderer.draw(game);
  const par = parTarget(levelNumber(target));
  const parSuffix = par !== null ? ` — par ${par} pushes` : "";
  const tier = difficultyTier(levelNumber(target));
  const diffSuffix = tier ? ` — ${tier}` : "";
  setStatus(`Level ${game.level.name} — ${game.boxes.length} boxes${parSuffix}${diffSuffix}`);
  updateValveButtons();
}

function refreshStatus(): void {
  if (!game) return;
  const par = parTarget(levelNumber(game.level));
  const parSuffix = par !== null ? ` / par ${par}` : "";
  setStatus(`Level ${game.level.name} — moves ${game.moves}, pushes ${game.pushes}${parSuffix}`);
  updateValveButtons();
}

function onSolved(): void {
  if (!game) return;
  locked = true;
  const lvl = game.level;
  const solved = lvl.name;

  if (slot && session) {
    const n = levelNumber(lvl);
    session.reportSolved(n, game.pushes);
    rebuildSelector(); // mark the just-solved option
    const par = parTarget(n);
    let parNote = "";
    if (par !== null) {
      parNote = session.isLevelPar(n)
        ? ` ✓ under par (${par})!`
        : ` (par ${par} — par check missed)`;
    }
    const next = nextPlayable(n);
    setStatus(
      next
        ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes)${parNote} → next…`
        : `Solved ${solved}! (${game.pushes} pushes)${parNote} No more playable levels right now — open a world or check your goal.`,
      true,
    );
    if (next) window.setTimeout(() => loadLevel(next.index), 1100);
    return;
  }

  const hasNext = current < levels.length - 1;
  setStatus(
    hasNext
      ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes) → next…`
      : `Solved ${solved}! That's the last level. 🎉`,
    true,
  );
  if (hasNext) window.setTimeout(() => loadLevel(current + 1), 1100);
}

function move(dir: Dir): void {
  if (!game || locked) return;
  if (!game.move(effectiveDir(dir, reversedControls))) return;
  renderer.draw(game);
  if (game.isWin()) onSolved();
  else refreshStatus();
}

function restart(): void {
  if (!game) return;
  game.restart();
  locked = false;
  renderer.draw(game);
  refreshStatus();
}

// --- Escape valves (AP mode) -----------------------------------------------

/** Undo the last move. Free offline; consumes an Undo Charge when connected. */
function undo(): void {
  if (!game || locked || !game.canUndo()) return;
  if (slot && session && !session.useUndo()) {
    setStatus("No Undo Charges available.");
    return;
  }
  if (game.undo()) {
    renderer.draw(game);
    refreshStatus();
  }
}

/** Reveal the next solution move by replaying a restart-aligned prefix (AP mode). */
function useHint(): void {
  if (!game || locked || !slot || !session) return;
  const n = levelNumber(game.level);
  const solution = solutions.get(n);
  if (!solution) {
    setStatus("No hint is available for this level.");
    return;
  }
  const moves = parseSolution(solution);
  if (hintIndex >= moves.length - 1) {
    setStatus("Hint: you're at the final step — finish it yourself! 🙂");
    return;
  }
  if (!session.useHint()) {
    setStatus("No Hint Tokens available.");
    return;
  }
  hintIndex += 1;
  replaySolutionPrefix(game, moves, hintIndex); // realign to the solution line, replay the prefix
  renderer.draw(game);
  setStatus(`Hint: replayed ${hintIndex}/${moves.length} solution moves.`);
  updateValveButtons();
}

/** Consume a Skip Token to clear the current level (sends its check), then advance. */
function useSkip(): void {
  if (!game || !slot || !session) return;
  const n = levelNumber(game.level);
  if (!session.useSkip(n)) {
    setStatus("No Skip Tokens available (or already solved).");
    return;
  }
  locked = true;
  setStatus(`Skipped level ${n} — check sent.`, true);
  rebuildSelector();
  const next = nextPlayable(n);
  if (next) window.setTimeout(() => loadLevel(next.index), 900);
}

/** Apply a (presentation-only) trap effect — never alters the solvable board. */
function triggerTrap(variant: TrapVariant): void {
  if (variant === "reversed") {
    reversedControls = true;
    setStatus("⚡ Trap: Reversed Controls — until you change levels!");
    return;
  }
  const cls = variant === "scramble" ? "trap-scramble" : "trap-decoy";
  canvas.classList.add(cls);
  window.setTimeout(() => canvas.classList.remove(cls), 1500);
  setStatus(variant === "scramble" ? "⚡ Trap: Scramble!" : "⚡ Trap: Decoy Box!");
}

/** Sync the valve buttons' labels/counts and enabled state with the session. */
function updateValveButtons(): void {
  const ap = Boolean(slot && session);
  hintBtn.hidden = !ap;
  skipBtn.hidden = !ap;
  const canUndo = Boolean(game?.canUndo()) && !locked;
  if (ap && session) {
    const a = session.available;
    undoBtn.textContent = `Undo (${a.undo})`;
    undoBtn.disabled = !canUndo || a.undo <= 0;
    hintBtn.textContent = `Hint (${a.hint})`;
    hintBtn.disabled = a.hint <= 0 || locked;
    skipBtn.textContent = `Skip (${a.skip})`;
    skipBtn.disabled =
      a.skip <= 0 || locked || (game ? session.isLevelSolved(levelNumber(game.level)) : true);
  } else {
    undoBtn.textContent = "Undo";
    undoBtn.disabled = !canUndo;
  }
}

// --- AP connection ---------------------------------------------------------

function handleDisconnect(): void {
  session = null;
  slot = null;
  connectBtn.textContent = "Connect";
  connectBtn.disabled = false;
  setConnStatus("Disconnected — free play (all levels).");
  rebuildSelector();
  loadLevel(0);
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
      rebuildSelector();
      const first = nextPlayable(0);
      if (first) loadLevel(first.index);
    },
    onUpdate: () => rebuildSelector(),
    onGoal: () => setConnStatus(`Goal complete! 🏆 (${slot?.goal})`, "ok"),
    onMessage: (text) => setStatus(text),
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

/** Fetch the single bundled manifest: boards (rendered) + solutions (hints). */
async function loadCorpus(): Promise<void> {
  const res = await fetch(MANIFEST_URL);
  if (!res.ok) throw new Error(`failed to load ${MANIFEST_URL}: ${res.status}`);
  const entries = (await res.json()) as ManifestEntry[];
  levels = entries.map((e) => levelFromBoard(e.board, e.n - 1, e.name));
  solutions = new Map(entries.filter((e) => e.solution).map((e) => [e.n, e.solution as string]));
}

async function main(): Promise<void> {
  setStatus("Loading levels…");
  await loadCorpus();

  const prefs = loadPrefs();
  if (prefs) {
    hostInput.value = prefs.host;
    slotInput.value = prefs.slot;
  }

  rebuildSelector();
  select.addEventListener("change", () => loadLevel(Number(select.value)));
  restartBtn.addEventListener("click", restart);
  undoBtn.addEventListener("click", undo);
  hintBtn.addEventListener("click", useHint);
  skipBtn.addEventListener("click", useSkip);
  connectBtn.addEventListener("click", onConnectClick);
  attachInput({ onMove: move, onRestart: restart, onUndo: undo, onHint: useHint, onSkip: useSkip });

  loadLevel(0);
}

main().catch((err) => {
  console.error(err);
  setStatus(`Error: ${msg(err)}`);
});
