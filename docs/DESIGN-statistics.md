# Design: per-level play statistics (visits + per-solve event log)

Status: **shipped in 0.6.0.** Records how often and how well each level is played, in both
solo free-play and AP-connected play, with JSON export/import for offline cross-player
analysis. The generator is unaffected; this is purely client state.

## Motivation

We want to see how levels actually play out — how many times a puzzle is opened, and the
moves / pushes / time of each solve — both for a single player over time and, by exporting
and pooling files, **across players** (e.g. the distribution of moves-per-solve for a given
level). The public site is a static GitHub Pages build with no backend, so cross-player
aggregation is done offline from exported files rather than a hosted telemetry sink.

## Data model

Per level, per corpus (`client/src/stats.ts`):

```ts
LevelStat  = { visits: number; sessions: string[]; solves: SolveEvent[] }
SolveEvent = { moves: number; pushes: number; timeMs: number; ts: number }
```

- **visits** — times the level was *opened* (`loadLevel`). A restart is the same visit.
- **sessions** — the set of page-load `sessionId`s that visited; **uniqueVisits** is the
  derived `new Set(sessions).size` (distinct play sessions). A random `sessionId` is minted
  once per page load.
- **solves** — one entry per solve. **bestMoves / bestPushes / bestTimeMs** are derived as
  the min over the log. `timeMs` is wall-clock from the start of the attempt (level load or
  restart) to the win; pauses and hint animations run the clock (a known simplification).
- A Skip-Token clear records no solve event (no real moves/time).

`derive(stat)` rolls a record up into the display view; the HUD shows live moves / pushes /
time chips plus `plays` (visits, with session count) and a `best` chip on solved levels.

## Persistence

- **Solo** (`SoloStats` in `stats.ts`): `localStorage` key `sokopelago.stats.v1`, shape
  `{ [corpus]: { [n]: LevelStat } }`. Loaded at startup, saved on each visit/solve.
- **AP-connected** (`client/src/ap/session.ts`): the AP server's **DataStorage**, scoped by
  seed + player: `sokopelago:<seed>:<player>:stats:{visits|sessions|solves}:<n>`. Visits use
  an atomic `add(1)`; the session id is appended once; solve events are appended with the
  array form `prepare(key, []).add([event]).commit()`. `loadStats()` batch-fetches every seed
  level on connect, so stats survive reconnects (appends fire only on the live event, never on
  the reconnect backlog, so nothing double-counts).

## Export / import (cross-player analysis)

The **Export stats** button downloads a JSON file:

```json
{ "schema": "sokopelago-stats/1", "player": "...", "exportedAt": 0,
  "corpora": { "microban": { "12": { "visits": 5, "sessions": ["..."], "solves": [ ... ] } } } }
```

It includes the solo store plus the live AP-session stats (current corpus) when connected.
**Import stats…** merges a file into the local solo store (summed visits, unioned sessions,
concatenated solve logs).

To analyze **across players**: collect each player's export, then group by `corpora[corpus][n]`
and pool the `solves` arrays — e.g. the moves/pushes/time distribution per level, or
fastest/fewest leaderboards. The flat, schema-tagged shape is meant to `JSON.parse` + concat.

## Out of scope (possible follow-ups)

- A hosted telemetry endpoint for automatic cross-player collection (needs infra + an
  opt-in/privacy story).
- Pause-aware timing; per-attempt (not just per-solve) event records.
