// Phase 0 local play loop: fetch corpus -> parse -> model -> render -> input.
// No Archipelago connection; just play the Microban levels in the browser.

import { parseXsb } from "./xsb";
import { Game } from "./board";
import { Renderer } from "./render";
import { attachInput } from "./input";
import type { Level } from "./types";

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

const renderer = new Renderer(canvas);

let levels: Level[] = [];
let game: Game | null = null;
let current = 0;
let locked = false; // briefly true between solving and auto-advancing

function setStatus(text: string, win = false): void {
  statusEl.textContent = text;
  statusEl.classList.toggle("win", win);
}

function loadLevel(i: number): void {
  current = Math.max(0, Math.min(levels.length - 1, i));
  select.value = String(current);
  game = new Game(levels[current]);
  locked = false;
  renderer.draw(game);
  setStatus(`Level ${game.level.name} — ${game.boxes.length} boxes`);
}

function refreshStatus(): void {
  if (!game) return;
  setStatus(
    `Level ${game.level.name} — moves ${game.moves}, pushes ${game.pushes}`,
  );
}

function onSolved(): void {
  if (!game) return;
  locked = true;
  const solved = game.level.name;
  const hasNext = current < levels.length - 1;
  setStatus(
    hasNext
      ? `Solved ${solved}! (${game.moves} moves, ${game.pushes} pushes) → next…`
      : `Solved ${solved}! That's the last level. 🎉`,
    true,
  );
  if (hasNext) {
    window.setTimeout(() => loadLevel(current + 1), 1100);
  }
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

async function main(): Promise<void> {
  setStatus("Loading levels…");
  const res = await fetch(CORPUS_URL);
  if (!res.ok) throw new Error(`failed to load ${CORPUS_URL}: ${res.status}`);
  levels = parseXsb(await res.text());

  select.innerHTML = "";
  for (const lvl of levels) {
    const opt = document.createElement("option");
    opt.value = String(lvl.index);
    opt.textContent = `${lvl.index + 1}. ${lvl.name}`;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => loadLevel(Number(select.value)));
  restartBtn.addEventListener("click", restart);
  attachInput({ onMove: move, onRestart: restart });

  loadLevel(0);
}

main().catch((err) => {
  console.error(err);
  setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
});
