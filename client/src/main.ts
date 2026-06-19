// Play loop: fetch corpus -> parse -> model -> render -> input.
//
// Two modes share one board:
//   - Offline (default): play any of the 155 Microban levels locally, no server.
//   - AP-connected: the selector shows only the seed's levels, gated by received
//     world keys; solving a level reports a check; meeting the goal reports GOAL.

import { parseXsb } from "./xsb";
import { Game } from "./board";
import { Renderer } from "./render";
import { attachInput } from "./input";
import type { Level } from "./types";
import { Session, loadPrefs, type SessionCallbacks } from "./ap/session";
import type { SlotData } from "./ap/slotData";

const CORPUS_URL = "/levels/microban.xsb";

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
};

const canvas = $<HTMLCanvasElement>("board");
const select = $<HTMLSelectElement>("level-select");
const restartBtn = $<HTMLButtonElement>("restart-btn");
const statusEl = $<HTMLDivElement>("status");
const hostInput = $<HTMLInputElement>("ap-host");
const slotInput = $<HTMLInputElement>("ap-slot");
const passInput = $<HTMLInputElement>("ap-pass");
const connectBtn = $<HTMLButtonElement>("ap-connect");
const connStatusEl = $<HTMLDivElement>("conn-status");

const renderer = new Renderer(canvas);

let levels: Level[] = [];
let game: Game | null = null;
let current = 0;
let locked = false; // briefly true between solving and auto-advancing

let session: Session | null = null;
let slot: SlotData | null = null; // non-null once connected (AP mode)

const msg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/** Microban level number (1-based) for a parsed level (index is 0-based). */
const levelNumber = (lvl: Level): number => lvl.index + 1;

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
  const base = `${levelNumber(lvl)}. ${lvl.name}`;
  if (!slot || !session) return base;
  const n = levelNumber(lvl);
  if (session.isLevelSolved(n)) return `✓ ${base}`;
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
  renderer.draw(game);
  setStatus(`Level ${game.level.name} — ${game.boxes.length} boxes`);
}

function refreshStatus(): void {
  if (!game) return;
  setStatus(`Level ${game.level.name} — moves ${game.moves}, pushes ${game.pushes}`);
}

function onSolved(): void {
  if (!game) return;
  locked = true;
  const lvl = game.level;
  const solved = lvl.name;

  if (slot && session) {
    const n = levelNumber(lvl);
    session.reportSolved(n);
    rebuildSelector(); // mark the just-solved option
    const next = nextPlayable(n);
    setStatus(
      next
        ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes) → next…`
        : `Solved ${solved}! No more playable levels right now — open a world or check your goal.`,
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

function move(dir: "up" | "down" | "left" | "right"): void {
  if (!game || locked) return;
  if (!game.move(dir)) return;
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

async function main(): Promise<void> {
  setStatus("Loading levels…");
  const res = await fetch(CORPUS_URL);
  if (!res.ok) throw new Error(`failed to load ${CORPUS_URL}: ${res.status}`);
  levels = parseXsb(await res.text());

  const prefs = loadPrefs();
  if (prefs) {
    hostInput.value = prefs.host;
    slotInput.value = prefs.slot;
  }

  rebuildSelector();
  select.addEventListener("change", () => loadLevel(Number(select.value)));
  restartBtn.addEventListener("click", restart);
  connectBtn.addEventListener("click", onConnectClick);
  attachInput({ onMove: move, onRestart: restart });

  loadLevel(0);
}

main().catch((err) => {
  console.error(err);
  setStatus(`Error: ${msg(err)}`);
});
