// Puzzle of the Day — a standalone, OFFLINE page. It picks one corpus level per UTC calendar
// day (same for every client worldwide), runs the shared play engine, and after a solve (or an
// explicit give-up) collects a fun + difficulty rating, posting it to the owned backend. A
// minimal "today's results" view closes the loop.
//
// MODULE BOUNDARY: this file and everything under potd/** import only from engine/** and their
// own files — never ap/** or main.ts (enforced by dependency-cruiser + a guard test). POTD is
// offline; there is no AP session here.

import { Game } from "./engine/board";
import { Renderer } from "./engine/render";
import { attachInput } from "./engine/input";
import { levelFromBoard } from "./engine/xsb";
import type { Level } from "./engine/types";
import { fetchManifest, type ManifestEntry } from "./engine/manifest";
import { SoloStats, sessionId, visitorId, type SolveEvent } from "./engine/stats";
import {
  parseSolution,
  planHint,
  animateSolutionPrefix,
  type AnimationHandle,
  type Move,
} from "./engine/solution";
import { corpusLabel } from "./corpusLabel";
import { todaysIndex, utcDayString } from "./potd/select";
import { buildDailyPool, parseSource, handleDisplay } from "./potd/pool";
import {
  buildRatingEvent,
  postRating,
  postVisit,
  flushQueue,
  type RatingEvent,
} from "./potd/rating";

// The daily puzzle is drawn from the curated cross-corpus pool (see potd/pool.ts).
const POOL_CORPUS = "curated";
const API_BASE = import.meta.env.VITE_POTD_API; // undefined in dev/preview → ratings queue locally
const CLIENT_VERSION = __APP_VERSION__;
const HANDLE_KEY = "sokopelago.potd.handle";
const ratedKey = (date: string): string => `sokopelago.potd.rated.${date}`;

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
};

const canvas = $<HTMLCanvasElement>("board");
const titleEl = $<HTMLDivElement>("puzzle-title");
const statusEl = $<HTMLDivElement>("status");
const statsEl = $<HTMLDivElement>("stats");
const noticeEl = $<HTMLDivElement>("notice");
const restartBtn = $<HTMLButtonElement>("restart-btn");
const undoBtn = $<HTMLButtonElement>("undo-btn");
const hintBtn = $<HTMLButtonElement>("hint-btn");
const giveupBtn = $<HTMLButtonElement>("giveup-btn");
const shareBtn = $<HTMLButtonElement>("share-btn");
const handleInput = $<HTMLInputElement>("handle-input");
const handleSaveBtn = $<HTMLButtonElement>("handle-save");
const handleIdEl = $<HTMLSpanElement>("handle-id");
const ratePanel = $<HTMLDivElement>("rate-panel");
const funGroup = $<HTMLDivElement>("fun-group");
const diffGroup = $<HTMLDivElement>("diff-group");
const rateSubmit = $<HTMLButtonElement>("rate-submit");
const rateStatus = $<HTMLDivElement>("rate-status");
const resultsEl = $<HTMLDivElement>("results");

const renderer = new Renderer(canvas);

// --- Today's puzzle ---------------------------------------------------------

const today = utcDayString(new Date());
let level: Level | null = null;
let corpus = POOL_CORPUS; // the pick's source corpus (e.g. "sasquatch7"); set in main()
let levelN = 0; // the pick's level number within that source corpus
let solution: Move[] | null = null;

let game: Game | null = null;
const soloStats = new SoloStats(); // reuse the shipped stats model (visits + solve log)
let attemptStart = Date.now();
let attempts = 0; // board loads/restarts for this puzzle this session
let usedHint = false;
let hintBoxMoves = 0;
let hintAnim: AnimationHandle | null = null;
let animating = false;
let finished = false; // solved or gave up — the play loop stops accepting input changes
let ratingSent = false;

// --- Small DOM helpers ------------------------------------------------------

function setStatus(text: string, win = false): void {
  statusEl.textContent = text;
  statusEl.classList.toggle("win", win);
}

let noticeTimer: number | undefined;
function notice(text: string, ms = 5000): void {
  noticeEl.textContent = text;
  noticeEl.classList.remove("fading");
  if (noticeTimer !== undefined) window.clearTimeout(noticeTimer);
  noticeTimer = window.setTimeout(() => noticeEl.classList.add("fading"), ms);
}

// The canonical Pages URL is hardcoded so a shared link always points at the live page (not
// localhost/preview). Offline-safe: uses only the browser Clipboard API — no network dependency.
const SHARE_URL = "https://wcoldren.github.io/sokopelago/potd/";
async function copyShareLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(SHARE_URL);
    notice("Link copied — share today's puzzle!");
  } catch {
    notice(`Copy this link: ${SHARE_URL}`); // clipboard blocked (e.g. insecure context)
  }
}

function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
}

function chip(label: string, value: string): HTMLSpanElement {
  const el = document.createElement("span");
  el.className = "chip";
  const l = document.createElement("span");
  l.className = "label";
  l.textContent = label;
  el.append(l, document.createTextNode(value));
  return el;
}

function renderStats(): void {
  statsEl.replaceChildren();
  if (!game) return;
  statsEl.append(chip("moves", String(game.moves)));
  statsEl.append(chip("pushes", String(game.pushes)));
  statsEl.append(chip("time", formatMs(Date.now() - attemptStart)));
  undoBtn.disabled = !game.canUndo() || finished || animating;
  hintBtn.disabled = !solution || finished || animating;
}

// --- Play loop --------------------------------------------------------------

function beginAttempt(): void {
  attemptStart = Date.now();
  attempts += 1;
}

function loadPuzzle(): void {
  if (!level) return;
  game = new Game(level);
  beginAttempt();
  soloStats.recordVisit(corpus, levelN);
  hintBoxMoves = 0;
  renderer.draw(game);
  setStatus(`${corpusLabel(corpus)} #${levelN} — make your moves!`);
  renderStats();
}

function move(dir: Parameters<Game["move"]>[0]): void {
  if (!game || finished || animating) return;
  if (!game.move(dir)) return;
  renderer.draw(game);
  afterBoardChange();
}

function afterBoardChange(): void {
  if (!game) return;
  if (game.isWin()) {
    onSolved();
    return;
  }
  renderStats();
}

function restart(): void {
  if (!game || finished) return;
  hintAnim?.cancel();
  hintAnim = null;
  animating = false;
  game.restart();
  beginAttempt();
  renderer.draw(game);
  renderStats();
}

function undo(): void {
  if (!game || finished || animating || !game.canUndo()) return;
  if (game.hasBoxMove()) {
    let step: ReturnType<Game["undoStep"]>;
    do {
      step = game.undoStep();
    } while (step === "walk");
  } else {
    game.undoStep();
  }
  renderer.draw(game);
  renderStats();
}

/** Reveal the next push of the optimal line (free; flags the rating's usedHint). */
function useHint(): void {
  if (!game || finished || animating || !solution) return;
  usedHint = true;
  const plan = planHint(hintBoxMoves, 1, solution);
  if (plan.atEnd) {
    notice("Hint: you're at the final push — finish it yourself! 🙂");
    return;
  }
  hintBoxMoves = plan.boxMoves;
  const shown = plan.boxMoves;
  animating = true;
  renderStats();
  const g = game;
  const sol = solution;
  hintAnim = animateSolutionPrefix(g, sol, plan.moveCount, {
    onStep: () => {
      renderer.draw(g);
      setStatus(
        shown > 0 ? `Hint: showing the first ${shown} push(es)…` : "Hint: walk to the box…",
      );
    },
    onDone: () => {
      animating = false;
      hintAnim = null;
      setStatus(shown > 0 ? `Hint: first ${shown} push(es) shown. Your move!` : "Hint: your move!");
      renderStats();
    },
  });
}

function onSolved(): void {
  if (!game || finished) return;
  const ev: SolveEvent = {
    moves: game.moves,
    pushes: game.pushes,
    timeMs: Math.max(0, Date.now() - attemptStart),
    ts: Date.now(),
  };
  soloStats.recordSolve(corpus, levelN, ev);
  finished = true;
  setStatus(`Solved in ${game.moves} moves, ${game.pushes} pushes! 🎉`, true);
  renderStats();
  openRatePanel(true);
}

/** Give up: record an unsolved attempt and still collect a rating (difficulty signal matters). */
function giveUp(): void {
  if (finished) return;
  finished = true;
  hintAnim?.cancel();
  animating = false;
  setStatus("Gave up for today — your rating still helps!");
  renderStats();
  openRatePanel(false);
}

// --- Rating panel -----------------------------------------------------------

let funValue = 0;
let diffValue = 0;
let solvedForRating = true;

/** Build a 1–5 button row into `group`, calling `onPick` with the chosen value. */
function buildScale(group: HTMLElement, onPick: (v: number) => void): void {
  group.replaceChildren();
  for (let v = 1; v <= 5; v++) {
    const b = document.createElement("button");
    b.className = "scale-btn";
    b.textContent = String(v);
    b.addEventListener("click", () => {
      onPick(v);
      for (const child of group.children) child.classList.toggle("picked", child === b);
    });
    group.append(b);
  }
}

function openRatePanel(solved: boolean): void {
  if (localStorage.getItem(ratedKey(today))) {
    rateStatus.textContent = "You've already rated today's puzzle — thanks!";
    ratePanel.hidden = false;
    rateSubmit.disabled = true;
    giveupBtn.hidden = true;
    return;
  }
  solvedForRating = solved;
  ratePanel.hidden = false;
  giveupBtn.hidden = true;
  rateSubmit.disabled = true;
  rateStatus.textContent = "How fun was it, and how hard?";
}

function refreshRateSubmit(): void {
  rateSubmit.disabled = funValue === 0 || diffValue === 0 || ratingSent;
}

function currentHandle(): string {
  return (localStorage.getItem(HANDLE_KEY) ?? handleInput.value).trim();
}

async function submitRating(): Promise<void> {
  if (!game && solvedForRating) return;
  const handle = currentHandle();
  if (!handle) {
    rateStatus.textContent = "Pick a handle first (above) so your rating has a name.";
    return;
  }
  const event: RatingEvent = buildRatingEvent({
    date: today,
    corpus,
    levelN,
    handle,
    visitorId,
    sessionId,
    solved: solvedForRating,
    attempts,
    moves: game ? game.moves : 0,
    pushes: game ? game.pushes : 0,
    timeMs: game ? Math.max(0, Date.now() - attemptStart) : 0,
    usedHint,
    fun: funValue,
    difficulty: diffValue,
    clientVersion: CLIENT_VERSION,
  });
  ratingSent = true;
  rateSubmit.disabled = true;
  const ok = await postRating(API_BASE, event);
  localStorage.setItem(ratedKey(today), "1"); // soft-guard: don't re-prompt this browser today
  rateStatus.textContent = ok
    ? "Thanks! Your rating was recorded."
    : "Saved locally — we'll send it when the backend is reachable.";
  void loadResults();
}

// --- Results view -----------------------------------------------------------

interface ResultsAggregate {
  date: string;
  count: number;
  uniqueVisitors: number;
  avgFun: number | null;
  avgDifficulty: number | null;
  solveRate: number | null;
  movesDistribution: { moves: number; count: number }[];
}

async function loadResults(): Promise<void> {
  if (!API_BASE) {
    resultsEl.textContent = "Today's results appear once the backend is configured.";
    return;
  }
  try {
    const res = await fetch(`${API_BASE.replace(/\/$/, "")}/results?date=${today}`);
    if (!res.ok) throw new Error(String(res.status));
    renderResults((await res.json()) as ResultsAggregate);
  } catch {
    resultsEl.textContent = "Couldn't load today's results.";
  }
}

function renderResults(agg: ResultsAggregate): void {
  resultsEl.replaceChildren();
  const visitors = agg.uniqueVisitors ?? 0;
  if (!agg.count) {
    resultsEl.textContent = visitors
      ? `${visitors} visitor${visitors === 1 ? "" : "s"} today — no ratings yet. Be the first!`
      : "No ratings yet today — be the first!";
    return;
  }
  const row = document.createElement("div");
  row.className = "stats";
  const fmt = (n: number | null, d = 1): string => (n === null ? "—" : n.toFixed(d));
  row.append(chip("ratings", String(agg.count)));
  row.append(chip("visitors", String(visitors)));
  row.append(chip("avg fun", fmt(agg.avgFun)));
  row.append(chip("avg difficulty", fmt(agg.avgDifficulty)));
  row.append(
    chip("solve rate", agg.solveRate === null ? "—" : `${Math.round(agg.solveRate * 100)}%`),
  );
  resultsEl.append(row);

  if (agg.movesDistribution.length) {
    const max = Math.max(...agg.movesDistribution.map((d) => d.count));
    const hist = document.createElement("div");
    hist.className = "hist";
    const heading = document.createElement("div");
    heading.className = "hint";
    heading.textContent = "Moves to solve (today):";
    resultsEl.append(heading);
    for (const d of [...agg.movesDistribution].sort((a, b) => a.moves - b.moves)) {
      const bar = document.createElement("div");
      bar.className = "bar-row";
      const label = document.createElement("span");
      label.className = "bar-label";
      label.textContent = String(d.moves);
      const bar2 = document.createElement("span");
      bar2.className = "bar";
      bar2.style.width = `${Math.max(4, (d.count / max) * 100)}%`;
      const n = document.createElement("span");
      n.className = "bar-count";
      n.textContent = String(d.count);
      bar.append(label, bar2, n);
      hist.append(bar);
    }
    resultsEl.append(hist);
  }
}

// --- Handle -----------------------------------------------------------------

/** Show the visitor-derived display id next to the handle, so duplicate handles stay distinct. */
function renderHandleId(handle: string): void {
  handleIdEl.textContent = handle ? `shown as ${handleDisplay(handle, visitorId)}` : "";
}

function refreshHandleUI(): void {
  const h = localStorage.getItem(HANDLE_KEY);
  if (h) {
    handleInput.value = h;
    handleSaveBtn.textContent = "Change";
  }
  renderHandleId(h ?? "");
}

function saveHandle(): void {
  const h = handleInput.value.trim();
  if (!h) {
    notice("Pick a handle (any non-personal name) so your ratings have a name.");
    return;
  }
  localStorage.setItem(HANDLE_KEY, h);
  handleSaveBtn.textContent = "Change";
  renderHandleId(h);
  notice(`Handle set to “${handleDisplay(h, visitorId)}”.`);
  refreshRateSubmit();
}

// --- Bootstrap --------------------------------------------------------------

async function main(): Promise<void> {
  titleEl.textContent = `Puzzle of the Day · ${today} (UTC)`;
  setStatus("Loading today's puzzle…");

  let pool: ManifestEntry[];
  try {
    pool = buildDailyPool(await fetchManifest(POOL_CORPUS));
  } catch (e) {
    setStatus(`Couldn't load the puzzle: ${e instanceof Error ? e.message : String(e)}`);
    return;
  }
  if (!pool.length) {
    setStatus("No puzzle available today.");
    return;
  }
  const entry = pool[todaysIndex(pool.length, new Date())];
  const src = parseSource(entry.source, entry.n);
  corpus = src.corpus;
  levelN = src.n;
  level = levelFromBoard(entry.board, entry.n - 1, `${corpusLabel(corpus)} #${levelN}`);
  solution = entry.solution ? parseSolution(entry.solution) : null;
  titleEl.textContent = `Puzzle of the Day · ${today} (UTC) — ${corpusLabel(corpus)} #${levelN}`;

  buildScale(funGroup, (v) => {
    funValue = v;
    refreshRateSubmit();
  });
  buildScale(diffGroup, (v) => {
    diffValue = v;
    refreshRateSubmit();
  });

  restartBtn.addEventListener("click", restart);
  undoBtn.addEventListener("click", undo);
  hintBtn.addEventListener("click", useHint);
  giveupBtn.addEventListener("click", giveUp);
  shareBtn.addEventListener("click", () => void copyShareLink());
  handleSaveBtn.addEventListener("click", saveHandle);
  rateSubmit.addEventListener("click", () => void submitRating());
  attachInput({ onMove: move, onRestart: restart, onUndo: undo, onHint: useHint });

  refreshHandleUI();
  loadPuzzle();
  void postVisit(API_BASE, today, visitorId); // fire-and-forget unique-visit beacon
  void flushQueue(API_BASE); // retry any ratings stranded by an earlier offline solve
  void loadResults();
}

main().catch((err: unknown) => {
  console.error(err);
  setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
});
