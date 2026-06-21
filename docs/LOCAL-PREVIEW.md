# Local preview — Puzzle of the Day

Two ways to run the POTD page locally. **Local only** — neither deploys anything, touches secrets,
or talks to production.

| | Mode A — static layout preview | Mode B — full local loop |
|---|---|---|
| Command | `cd client && npm run dev:potd` | `cd client && npm run dev:full` |
| Backend | none (`VITE_POTD_API` unset) | local Worker (`wrangler dev`) + local D1 |
| Rating POST | fails → queued in `localStorage` (nothing persists) | succeeds → row in the **local** D1 |
| Results view | shows "appears once the backend is configured" | shows live counts/averages/histogram |
| Use it for | eyeballing layout + play feel | end-to-end solve → rate → results |

URLs (both modes open `/potd.html` automatically): Vite at **http://localhost:5173**, and in Mode B
the Worker at **http://localhost:8787**.

## Mode A — static layout preview (no backend)

```sh
cd client
npm run dev:potd        # vite --open /potd.html, no VITE_POTD_API
```

Play and rate as normal. Because no API base is configured, each submitted rating drops straight
into the `localStorage` retry queue (`sokopelago.potd.queue.v1`) — expected, and nothing is lost.
The results panel stays in its degraded state. Good for iterating on layout/CSS/play feel.

## Mode B — full local loop (ratings actually save)

```sh
cd client
npm run dev:full
```

`dev:full` runs the whole loop:

1. **`predev:full`** applies `schema.sql` to the **local** D1 first
   (`npm --prefix ../server/potd-worker run db:local`; the DDL is `CREATE … IF NOT EXISTS`, so
   re-running is safe).
2. `concurrently` then starts both processes:
   - the Worker via `wrangler dev` (local mode, local D1) on `:8787`, and
   - Vite with `VITE_POTD_API=http://localhost:8787`, pinned to `:5173` (`--strictPort`) so its
     origin matches the Worker's CORS allow-list (`ALLOWED_ORIGINS` in
     `server/potd-worker/wrangler.toml`).

Solve today's puzzle, submit a rating, and it persists to the local D1 and shows up in the results
view (a `POST /ratings` followed by `GET /results?date=<today>`). `Ctrl-C` stops both (`-k`).

### Local D1 data is separate and safe to wipe

The local database lives under `server/potd-worker/.wrangler/` (git-ignored) and has **nothing** to
do with production. Reset it any time:

```sh
rm -rf server/potd-worker/.wrangler   # then `npm run dev:full` re-applies the schema
```

## Notes

- Need the Worker on its own? `cd server/potd-worker && npm run dev`. Apply/refresh the local
  schema with `npm run db:local` (and `npm run db:remote` for the deployed D1, after setup).
- Deploy + first-time D1 setup live in [`server/potd-worker/README.md`](../server/potd-worker/README.md).
