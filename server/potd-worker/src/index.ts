// Sokopelago Puzzle-of-the-Day ratings sink — a dependency-light Cloudflare Worker over D1.
//
// Three endpoints, append-only:
//   POST /ratings              -> validate one rating event, insert one row, 204
//   POST /visit                -> record a unique (date, visitorId) visit, 204
//   GET  /results?date=YYYY-MM-DD -> today's aggregates for the client's results view
//
// CORS is allow-listed to the Pages origin(s) in ALLOWED_ORIGINS. No auth in v1 (see the
// spam TODO below). No personal data is stored — only the player's self-chosen handle.

export interface Env {
  DB: D1Database;
  /** Comma-separated exact origins allowed to call this Worker (the Pages site[s]). */
  ALLOWED_ORIGINS: string;
}

// Bumped to /2 with the addition of `visitorId`. MUST stay in lockstep with the client's
// RATING_SCHEMA + validateRatingEvent — see client/src/potd/rating.ts.
const RATING_SCHEMA = "sokopelago-potd-rating/2";
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// --- CORS -------------------------------------------------------------------

function allowedOrigins(env: Env): Set<string> {
  return new Set(
    (env.ALLOWED_ORIGINS ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

/** CORS headers for an allowed origin, or null if the origin isn't on the allow-list. */
function corsHeaders(origin: string | null, env: Env): Record<string, string> | null {
  if (!origin || !allowedOrigins(env).has(origin)) return null;
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(body: unknown, status: number, cors: Record<string, string> | null): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...(cors ?? {}) },
  });
}

// --- Validation (mirrors client/src/potd/rating.ts — keep in sync) ----------

function isInt(v: unknown): v is number {
  return typeof v === "number" && Number.isInteger(v);
}
function isNonNegNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v) && v >= 0;
}
function isRating(v: unknown): v is number {
  return isInt(v) && v >= 1 && v <= 5;
}
function isNonEmptyStr(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

interface RatingEvent {
  schema: string;
  date: string;
  corpus: string;
  levelN: number;
  handle: string;
  visitorId: string;
  sessionId: string;
  solved: boolean;
  attempts: number;
  moves: number;
  pushes: number;
  timeMs: number;
  usedHint: boolean;
  fun: number;
  difficulty: number;
  clientVersion: string;
}

function validate(value: unknown): value is RatingEvent {
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
    isNonEmptyStr(e.visitorId) &&
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

// --- Handlers ---------------------------------------------------------------

async function postRating(
  req: Request,
  env: Env,
  cors: Record<string, string> | null,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400, cors);
  }
  if (!validate(body)) return json({ error: "invalid rating event" }, 400, cors);
  const e = body;

  // Spam baseline: one rating per (date, level_n, visitor_id). INSERT OR IGNORE drops a casual
  // re-submit at write time (the UNIQUE constraint in schema.sql), so a single visitor can't flood
  // one puzzle. No auth/secret, so the page stays offline-capable. A stronger gate (shared token,
  // hashed-IP rate analysis, Turnstile) is deferred until there's evidence of real abuse.
  await env.DB.prepare(
    `INSERT OR IGNORE INTO ratings
       (received_at, schema, date, corpus, level_n, handle, visitor_id, session_id,
        solved, attempts, moves, pushes, time_ms, used_hint, fun, difficulty, client_version)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
  )
    .bind(
      Date.now(), // received_at is server-set — never trusted from the client
      e.schema,
      e.date,
      e.corpus,
      e.levelN,
      e.handle,
      e.visitorId,
      e.sessionId,
      e.solved ? 1 : 0,
      e.attempts,
      e.moves,
      e.pushes,
      e.timeMs,
      e.usedHint ? 1 : 0,
      e.fun,
      e.difficulty,
      e.clientVersion,
    )
    .run();

  return new Response(null, { status: 204, headers: cors ?? {} });
}

async function postVisit(
  req: Request,
  env: Env,
  cors: Record<string, string> | null,
): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400, cors);
  }
  const b = (body ?? {}) as Record<string, unknown>;
  if (typeof b.date !== "string" || !DATE_RE.test(b.date) || !isNonEmptyStr(b.visitorId)) {
    return json({ error: "invalid visit" }, 400, cors);
  }
  // INSERT OR IGNORE against the (date, visitor_id) primary key, so reloads dedup at write time.
  await env.DB.prepare(
    `INSERT OR IGNORE INTO visits (date, visitor_id, first_seen) VALUES (?,?,?)`,
  )
    .bind(b.date, b.visitorId, Date.now())
    .run();
  return new Response(null, { status: 204, headers: cors ?? {} });
}

interface AggRow {
  n: number;
  avg_fun: number | null;
  avg_diff: number | null;
  solve_rate: number | null;
}

async function getResults(
  url: URL,
  env: Env,
  cors: Record<string, string> | null,
): Promise<Response> {
  const date = url.searchParams.get("date") ?? "";
  if (!DATE_RE.test(date)) return json({ error: "bad or missing date" }, 400, cors);

  const agg = await env.DB.prepare(
    `SELECT COUNT(*) AS n, AVG(fun) AS avg_fun, AVG(difficulty) AS avg_diff,
            AVG(solved) AS solve_rate
       FROM ratings WHERE date = ?`,
  )
    .bind(date)
    .first<AggRow>();

  const dist = await env.DB.prepare(
    `SELECT moves, COUNT(*) AS count FROM ratings
       WHERE date = ? AND solved = 1 GROUP BY moves ORDER BY moves`,
  )
    .bind(date)
    .all<{ moves: number; count: number }>();

  const visits = await env.DB.prepare(`SELECT COUNT(*) AS n FROM visits WHERE date = ?`)
    .bind(date)
    .first<{ n: number }>();

  return json(
    {
      date,
      count: agg?.n ?? 0,
      uniqueVisitors: visits?.n ?? 0,
      avgFun: agg?.avg_fun ?? null,
      avgDifficulty: agg?.avg_diff ?? null,
      solveRate: agg?.solve_rate ?? null,
      movesDistribution: dist.results ?? [],
    },
    200,
    cors,
  );
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const origin = req.headers.get("Origin");
    const cors = corsHeaders(origin, env);

    // Reject browser cross-origin calls from origins not on the allow-list. A missing Origin
    // (non-browser client) isn't a CORS violation — let it through (the endpoint is public).
    if (origin && !cors) return new Response("forbidden origin", { status: 403 });

    if (req.method === "OPTIONS") {
      return new Response(null, { status: cors ? 204 : 403, headers: cors ?? {} });
    }

    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/ratings") return postRating(req, env, cors);
    if (req.method === "POST" && url.pathname === "/visit") return postVisit(req, env, cors);
    if (req.method === "GET" && url.pathname === "/results") return getResults(url, env, cors);
    return json({ error: "not found" }, 404, cors);
  },
};
