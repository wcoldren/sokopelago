// POTD rating events: the append-only data point sent to the owned backend after a solve (or an
// explicit give-up/skip). This module owns the payload shape, its validation, and a localStorage
// retry queue so a POST failure never loses a solve. It is offline/engine-only — it must never
// import from ap/** or main.ts (see the import-boundary check).

/** Schema tag carried on every event, bumped if the shape changes (analysis keys off it). */
export const RATING_SCHEMA = "sokopelago-potd-rating/1";

/** One rating + solve-stats data point for the Puzzle of the Day. */
export interface RatingEvent {
  schema: string;
  date: string; // UTC calendar day, YYYY-MM-DD (the puzzle key)
  corpus: string;
  levelN: number; // corpus level number (1-based)
  handle: string; // self-chosen, non-PII
  sessionId: string; // page-load session id (engine/stats.sessionId)
  solved: boolean; // false on an explicit give-up / skip
  attempts: number; // board loads/restarts for this puzzle this session
  moves: number;
  pushes: number;
  timeMs: number;
  usedHint: boolean;
  fun: number; // 1–5
  difficulty: number; // 1–5
  clientVersion: string;
}

/** Fields the caller supplies; `schema` is stamped here so callers can't get it wrong. */
export type RatingInput = Omit<RatingEvent, "schema">;

/** Assemble a complete, schema-tagged rating event from the play-loop's measured fields. */
export function buildRatingEvent(input: RatingInput): RatingEvent {
  return { schema: RATING_SCHEMA, ...input };
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const isNonNegNum = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v) && v >= 0;
const isRating = (v: unknown): v is number => isInt(v) && v >= 1 && v <= 5;
const isNonEmptyStr = (v: unknown): v is string => typeof v === "string" && v.length > 0;

/**
 * Validate an untrusted value as a well-formed RatingEvent. Mirrors the Worker's server-side
 * checks (kept in sync deliberately) so the client never queues a payload the server will 400.
 */
export function validateRatingEvent(value: unknown): value is RatingEvent {
  if (!value || typeof value !== "object") return false;
  const e = value as Record<string, unknown>;
  return (
    e.schema === RATING_SCHEMA &&
    typeof e.date === "string" &&
    DATE_RE.test(e.date) &&
    isNonEmptyStr(e.corpus) &&
    isInt(e.levelN) &&
    e.levelN >= 1 &&
    isNonEmptyStr(e.handle) &&
    typeof e.sessionId === "string" &&
    typeof e.solved === "boolean" &&
    isInt(e.attempts) &&
    e.attempts >= 0 &&
    isNonNegNum(e.moves) &&
    isNonNegNum(e.pushes) &&
    isNonNegNum(e.timeMs) &&
    typeof e.usedHint === "boolean" &&
    isRating(e.fun) &&
    isRating(e.difficulty) &&
    typeof e.clientVersion === "string"
  );
}

// --- localStorage retry queue ----------------------------------------------
// A POST failure (offline, Worker down, CORS) must never lose a solve: queue the event and
// retry on the next page load / explicit flush. The server is append-only, so a retried POST
// may duplicate — analysis dedups later by (sessionId, date, levelN). That's the accepted v1
// trade-off (collection-completeness over exactly-once).

const QUEUE_KEY = "sokopelago.potd.queue.v1";

function readQueue(): RatingEvent[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(validateRatingEvent) : [];
  } catch {
    return [];
  }
}

function writeQueue(events: RatingEvent[]): void {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(events));
  } catch {
    /* storage unavailable — keep whatever is in memory for this page */
  }
}

/** Append an event to the local retry queue. */
export function enqueueRating(event: RatingEvent): void {
  const q = readQueue();
  q.push(event);
  writeQueue(q);
}

/** POST one event. Resolves true on a 2xx, false on any network/HTTP failure. */
async function postOne(
  apiBase: string,
  event: RatingEvent,
  fetchFn: typeof fetch,
): Promise<boolean> {
  try {
    const res = await fetchFn(`${apiBase.replace(/\/$/, "")}/ratings`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(event),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Send `event` now, queueing it for later if the POST can't be made (no API base configured,
 * offline, or a non-2xx response). Returns true only when the server accepted it this call.
 */
export async function postRating(
  apiBase: string | undefined,
  event: RatingEvent,
  fetchFn: typeof fetch = fetch,
): Promise<boolean> {
  if (!apiBase) {
    enqueueRating(event);
    return false;
  }
  const ok = await postOne(apiBase, event, fetchFn);
  if (!ok) enqueueRating(event);
  return ok;
}

/**
 * Retry every queued event against the backend, dropping the ones the server accepts and
 * keeping the rest for the next flush. Returns the number successfully sent. A no-op without
 * an API base (nothing to retry against — the queue is preserved).
 */
export async function flushQueue(
  apiBase: string | undefined,
  fetchFn: typeof fetch = fetch,
): Promise<number> {
  if (!apiBase) return 0;
  const pending = readQueue();
  if (pending.length === 0) return 0;
  const remaining: RatingEvent[] = [];
  let sent = 0;
  for (const event of pending) {
    if (await postOne(apiBase, event, fetchFn)) sent += 1;
    else remaining.push(event);
  }
  writeQueue(remaining);
  return sent;
}
