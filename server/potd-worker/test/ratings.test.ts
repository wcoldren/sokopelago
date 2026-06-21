import { env } from "cloudflare:test";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import worker from "../src/index";
// Vite raw import: apply the same schema the deployment uses, so tests exercise the real DDL.
import schemaSql from "../src/schema.sql?raw";

const ORIGIN = "https://example.com"; // matches vitest.config.ts ALLOWED_ORIGINS

const goodEvent = {
  schema: "sokopelago-potd-rating/1",
  date: "2026-06-21",
  corpus: "microban",
  levelN: 12,
  handle: "boxpusher",
  sessionId: "s1",
  solved: true,
  attempts: 2,
  moves: 40,
  pushes: 18,
  timeMs: 53000,
  usedHint: false,
  fun: 4,
  difficulty: 3,
  clientVersion: "0.7.0",
};

async function applySchema(): Promise<void> {
  // Strip line comments first so no chunk is comment-only (D1 rejects a statement-less prepare).
  for (const stmt of schemaSql
    .replace(/--[^\n]*/g, "")
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean)) {
    await env.DB.prepare(stmt).run();
  }
}

function post(body: unknown, origin: string | null = ORIGIN): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (origin) headers.Origin = origin;
  return worker.fetch(
    new Request("https://worker/ratings", { method: "POST", headers, body: JSON.stringify(body) }),
    env,
  );
}

function getResults(date: string, origin: string | null = ORIGIN): Promise<Response> {
  const headers: Record<string, string> = {};
  if (origin) headers.Origin = origin;
  return worker.fetch(
    new Request(`https://worker/results?date=${date}`, { headers }),
    env,
  );
}

beforeAll(applySchema);
beforeEach(async () => {
  await env.DB.prepare("DELETE FROM ratings").run();
});

describe("POST /ratings", () => {
  it("appends a row and returns 204", async () => {
    const res = await post(goodEvent);
    expect(res.status).toBe(204);
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM ratings").first<{ n: number }>();
    expect(row?.n).toBe(1);
  });

  it("is append-only: a second identical POST adds another row (no dedup)", async () => {
    await post(goodEvent);
    await post(goodEvent);
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM ratings").first<{ n: number }>();
    expect(row?.n).toBe(2);
  });

  it("rejects a malformed payload with 400", async () => {
    expect((await post({ ...goodEvent, fun: 9 })).status).toBe(400);
    expect((await post({ ...goodEvent, date: "nope" })).status).toBe(400);
    expect((await post("not json at all")).status).toBe(400); // valid JSON string, bad shape
  });

  it("range-checks fun/difficulty server-side: rejects out-of-range and non-integer with 400", async () => {
    // The server never trusts the client: fun and difficulty must be integers in 1..5.
    for (const bad of [0, 6, 3.5, -1, "4", null]) {
      expect((await post({ ...goodEvent, fun: bad })).status).toBe(400);
      expect((await post({ ...goodEvent, difficulty: bad })).status).toBe(400);
    }
    // And nothing was written for any of those rejects.
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM ratings").first<{ n: number }>();
    expect(row?.n).toBe(0);
  });
});

describe("GET /results", () => {
  it("aggregates counts, averages, solve rate, and moves distribution", async () => {
    await post({ ...goodEvent, solved: true, fun: 5, difficulty: 2, moves: 40 });
    await post({ ...goodEvent, solved: false, fun: 3, difficulty: 4, moves: 0 });

    const res = await getResults("2026-06-21");
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      count: number;
      avgFun: number;
      avgDifficulty: number;
      solveRate: number;
      movesDistribution: { moves: number; count: number }[];
    };
    expect(body.count).toBe(2);
    expect(body.avgFun).toBeCloseTo(4); // (5 + 3) / 2
    expect(body.avgDifficulty).toBeCloseTo(3); // (2 + 4) / 2
    expect(body.solveRate).toBeCloseTo(0.5); // 1 of 2 solved
    expect(body.movesDistribution).toEqual([{ moves: 40, count: 1 }]); // only the solved row
  });

  it("returns an empty aggregate for a day with no ratings", async () => {
    const body = (await (await getResults("2099-01-01")).json()) as { count: number };
    expect(body.count).toBe(0);
  });

  it("400s on a bad/missing date", async () => {
    expect((await getResults("06-21")).status).toBe(400);
  });
});

describe("CORS", () => {
  it("rejects a disallowed origin with 403 and no ACAO header", async () => {
    const res = await post(goodEvent, "https://evil.example");
    expect(res.status).toBe(403);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("echoes the allow-listed origin on a preflight", async () => {
    const res = await worker.fetch(
      new Request("https://worker/ratings", { method: "OPTIONS", headers: { Origin: ORIGIN } }),
      env,
    );
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
  });
});
