## Sokopelago 0.8.0 — more corpora, bigger pools

> **Alpha (`0.x`).** Pre-1.0: the option/id layout may still move between releases. Players in a
> multiworld must all use the **same** apworld version. Drop `sokopelago.apworld` into your
> Archipelago `custom_worlds/` (or `worlds/`) folder.

What changed in the **apworld** this release:

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
