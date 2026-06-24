## Sokopelago 0.8.2 — fix Puzzle-of-the-Day data load

> **Alpha (`0.x`).** Pre-1.0: the option/id layout may still move between releases. Players in a
> multiworld must all use the **same** apworld version.

A client-only, contract-preserving patch — no item/location id, `slot_data`, or option-schema change.

- **Puzzle-of-the-Day now loads.** The `/potd/` page 404'd on its corpus data (`./data/curated.json`)
  because the manifest URL was route-relative and the page is served one level deep. The fetch now
  anchors to the app root, so it works from any route (dev / GitHub Pages / itch). The main game was
  unaffected.

---

## Sokopelago 0.8.1 — curated soundness + Puzzle-of-the-Day live

> **Alpha (`0.x`).** Pre-1.0: the option/id layout may still move between releases. Players in a
> multiworld must all use the **same** apworld version. Drop `sokopelago.apworld` into your
> Archipelago `custom_worlds/` (or `worlds/`) folder.

A contract-preserving patch — no item/location id, `slot_data`, or option-schema change, so it's
drop-in compatible with `0.8.0` seeds' settings (but see the curated re-index note).

- **Curated soundness fix:** the `curated` pool no longer contains pull-required levels, so a
  pull-logic-off seed can't strand a pure-push player on an unwinnable check. The builder re-indexes,
  so `curated` dropped 545 → 539 levels and its numbering shifted — **old `curated` seeds won't
  reproduce identically.** Other corpora are untouched.
- **Multiworld pull is gated behind `pull_logic`** (the expert `pullban` tier is unaffected); solo
  pull is now an explicit opt-in sandbox aid.
- **Puzzle-of-the-Day backend is live** with a server-side rating-dedup spam baseline; the page is
  reachable at a clean `/potd/` URL, cross-links with the main page, and has share/link-preview meta.

---

## Sokopelago 0.8.0 — more corpora, bigger pools

What changed in the **apworld** in 0.8.0:

- **Two new selectable corpora** (the `corpus` YAML option):
  - **`curated`** — a large, solved, merged & re-indexed pool drawn from Microban I–III,
    Sasquatch I–IX, XSokoban and more. The widest variety in one seed.
  - **`autoban`** — an in-house, push-only generated set with a calibrated easy/medium/hard
    spread (original by construction).
- **155-level id cap lifted** (`MAX_WORLDS` 155 → 198; "Solve …" locations registered up to the
  pool maximum), so big merged pools work at higher `levels_per_region`. **Fully
  backward-compatible** — every existing item/location id (1..155) is unchanged, so this is an
  additive minor bump and no existing seed breaks.
- **World 1 opener variation** — the first world's internal order is shuffled, so a seed no longer
  always starts on the same level.
- Bundled corpus data + the annotate/ingest/scoring/`build_pool` pipeline that produced it.

**Datapackage note:** additive only — new `corpus` option values and new item/location ids; no
existing id or `slot_data` field changed.

### Try it
A ready-to-run single-player config is attached (`Sokopelago-Easy.yaml`) — a gentle, easy-tier
Microban seed. Generate with it, or set `corpus: curated` / `corpus: autoban` to sample the new
pools. Requires Archipelago **0.6.7+**.

See the full list of changes in [`CHANGELOG.md`](https://github.com/wcoldren/sokopelago/blob/main/CHANGELOG.md)
and known rough edges in [`docs/KNOWN-ISSUES.md`](https://github.com/wcoldren/sokopelago/blob/main/docs/KNOWN-ISSUES.md).
