# Sokopelago POTD ratings Worker

A dependency-light **Cloudflare Worker + D1** that collects Puzzle-of-the-Day ratings from the
client and serves today's aggregates back. Append-only; no auth in v1.

- `POST /ratings` — validate one rating event, insert one row, return `204`.
- `POST /visit` — record a unique `(date, visitorId)` visit (`INSERT OR IGNORE`), return `204`.
- `GET /results?date=YYYY-MM-DD` — counts + unique visitors + average fun/difficulty + solve rate +
  a moves distribution for that UTC day.

**No personal data is collected.** The only identifiers are the player's **self-chosen handle**
(non-PII, a display label only), a random per-page-load session id, and a random, persisted
`visitorId` (non-PII) used to count unique visitors and disambiguate duplicate handles. CORS is
allow-listed to the Pages origin(s).

> These are the exact commands for **you** (the maintainer) to run. CI does not run any of the
> `wrangler d1 create` / deploy steps for you — it only runs `wrangler deploy` once the repo
> secrets exist (see the root CI section). Nothing here touches credentials in the repo.

## One-time setup

```sh
cd server/potd-worker
npm install                      # installs wrangler + the test pool (also creates package-lock.json)

# 1. Authenticate wrangler to your Cloudflare account (interactive, opens a browser):
npx wrangler login

# 2. Create the D1 database. Copy the printed `database_id` into wrangler.toml.
npx wrangler d1 create sokopelago-potd

# 3. Edit wrangler.toml:
#    - paste database_id under [[d1_databases]]
#    - set ALLOWED_ORIGINS to your exact Pages origin(s), comma-separated
#      e.g. "https://<username>.github.io" (add a custom domain if you have one)

# 4. Apply the schema to BOTH the local dev DB and the remote (production) DB:
npm run db:local
npm run db:remote
```

## Develop & test locally

```sh
npm test         # runs the Worker tests in workerd against a local D1 (no account needed)
npm run dev      # wrangler dev — serves the Worker locally with a local D1
npm run db:local # (re)apply src/schema.sql to the local D1
```

> **Tip:** to run the **whole** local loop (Worker + the POTD page wired to it, with the schema
> applied for you) in one command, use `cd ../../client && npm run dev:full`. The two preview
> modes are documented in [`docs/LOCAL-PREVIEW.md`](../../docs/LOCAL-PREVIEW.md).

## Deploy

Manual (from your machine, after `wrangler login`):

```sh
cd server/potd-worker
npx wrangler deploy
```

Automated via CI (`.github/workflows/ci.yml` → `deploy-worker` job): runs `wrangler deploy` on
pushes to `main` that touch `server/potd-worker/**`, using repo secrets **you** add:

- `CLOUDFLARE_API_TOKEN` — a scoped token with Workers + D1 edit permissions.
- `CLOUDFLARE_ACCOUNT_ID` — your account id (passed to wrangler via env).

The deploy job is **scaffolded but inert** until those secrets exist.

## Client build wiring

The client reads the backend origin from `VITE_POTD_API` at build time. For the production Pages
build this is committed in `client/.env.production` (`VITE_POTD_API=<worker-url>`); the URL is not
a secret. When unset (local dev/preview), the POTD page still plays and **queues ratings locally**
(retrying on the next load) and the visit beacon is a no-op — so the page is fully offline-tolerant.

The rating payload is the **`sokopelago-potd-rating/2`** schema. Its validator is mirrored, field
for field, between `src/index.ts` (`validate`) and `client/src/potd/rating.ts`
(`validateRatingEvent`); the `RATING_SCHEMA` tag is bumped in lockstep whenever the shape changes,
so a stale client can't post a payload the server will accept by accident.

## Notes / TODO

- **Spam:** no auth in v1. If abused, gate `POST /ratings` behind Cloudflare Turnstile or a
  shared token (checked in `src/index.ts`), and/or persist a salted hash of `CF-Connecting-IP`
  for rate analysis. Marked with a `TODO(spam)` in the source.
- **Dedup:** the `ratings` sink never dedups (it's append-only). "Already rated today" is a
  client-side `localStorage` soft-guard only; offline analysis dedups by `visitor_id + date`
  (stable across reloads/sessions). The `visits` table *does* dedup at write time on
  `(date, visitor_id)`, so `uniqueVisitors` is an honest count.
