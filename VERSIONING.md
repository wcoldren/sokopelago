# Versioning

Sokopelago follows [Semantic Versioning](https://semver.org/) with one project-specific
constraint: an Archipelago world must keep its **datapackage stable** (location/item IDs
and the name→id map) or it breaks existing seeds. That constraint drives what counts as a
breaking change.

## One version, two components

The project ships a **single version**, kept in lockstep across both components:

| Component | File | Field |
|-----------|------|-------|
| apworld   | `apworld/sokopelago/archipelago.json` | `world_version` |
| client    | `client/package.json` (+ `package-lock.json`) | `version` |

They release together because the client speaks the apworld's `slot_data` schema — bump
both, or neither.

`minimum_ap_version` in `archipelago.json` is **separate** from the project version. Bump
it only when the world starts relying on a newer Archipelago API; it does not follow the
project version.

## Current status: alpha (`0.x`)

We are pre-1.0. Per SemVer, the `0.x` line carries no stability promise — the public API,
`slot_data` schema, and ID layout may still move. The authoritative current version lives in
`apworld/sokopelago/archipelago.json` (`world_version`) and at the top of `CHANGELOG.md`; this
doc deliberately does not restate a version number (a hand-maintained one here only goes stale).

The minor digit bumps on each **contract**-affecting change — **not** per roadmap phase number,
and **not** on every change to generated output. History to date: `0.1.0` (Phase 1, world core)
→ `0.2.0` (Phase 3 valves) → `0.3.0` (Phase 4 par checks) → `0.4.0` (Phase 5 expert Pull tier) →
`0.5.0` (seed-varied selection + tiered par) → `0.6.0` (honest difficulty + easy-first options) →
`0.7.0` (accurate logic: boss-zone gate + count-floor chaining) → `0.8.0` (new `autoban` + `curated`
corpus options, 155-level id cap lifted) → `0.8.1` (contract-preserving patch: curated `requires_pull`
filter + multiworld pull gated behind `pull_logic`, POTD backend live with rating dedup) → `0.8.2`
(contract-preserving patch: fix the Puzzle-of-the-Day page's corpus-data load on the `/potd/`
sub-route). Phase 2 was a client-only integration milestone and rode along with no world bump.

### While `< 1.0.0`

The split is about **contracts**, not about whether generated output changed. A "contract" is
something another party depends on: the **datapackage** (location/item IDs + name→id map), the
**`slot_data` schema** the client reads, the **YAML option schema**, and **`minimum_ap_version`**.

- **MINOR** (`0.6 → 0.7`): a contract change — new/removed/renamed options, new items or
  locations (new IDs), a `slot_data` **schema** change, or a `minimum_ap_version` raise that
  invalidates existing seeds. (Pre-1.0 these "breaking" changes ride minor bumps.)
- **PATCH** (`0.7.0 → 0.7.1`): anything that preserves every contract — bug fixes,
  fill-robustness fixes, balance/difficulty/**corpus** tuning, default-value changes,
  client-only fixes, docs, tests. A patch **may change generated output**: pre-1.0, identical
  regeneration of a given (YAML, seed) is guaranteed only within the same version, and players
  sync the apworld version anyway — so changing *which* puzzles or item placements a seed
  produces is a patch, as long as the datapackage, `slot_data` schema, and option schema are
  untouched.

> Why output-changing patches are fine: the apworld *is* a generator, so almost every fix alters
> output. Tying the minor digit to "output changed" would make the patch level unusable and
> inflate the minor number on pure tuning. The datapackage / schema / option contracts are what
> actually break other parties, so those — and only those — drive a minor bump. (Example: adding
> push-solvable levels to the pullban corpus, reusing already-registered IDs, is a **patch**; it
> changes which puzzles a pullban seed draws but breaks no contract.)

## `1.0.0` — first stable release

Cut `1.0.0` when the feature set and ID layout are frozen enough to promise
compatibility (realistically once Phase 5/6 land and we're willing to support seeds long
term). From that point the rules below apply.

### While `>= 1.0.0`

- **MAJOR:** anything that breaks an existing seed or datapackage round-trip —
  reassigning or removing existing location/item IDs, changing the name→id map, removing
  or renaming options, or a `slot_data` schema change an older client can't read. Raising
  `minimum_ap_version` in a way that invalidates existing seeds is also major.
- **MINOR:** backward-compatible additions — new options that default to off, new
  locations/items assigned **new** stable IDs, client features that degrade gracefully on
  older slot_data.
- **PATCH:** bug fixes with no ID, schema, or option changes.

## The datapackage invariant

Once an ID is published, it is permanent: **never reassign or remove an existing location
or item ID, and never change the name→id mapping.** Add new IDs in fresh ranges instead.

This is already designed for: par-location names are registered globally regardless of
the `par_checks` toggle (`apworld/sokopelago/Locations.py`), so the name→id map is
identical whether or not par checks are enabled.

## Release checklist

1. Decide the bump using the rules above: a **contract** change (datapackage / `slot_data`
   schema / option schema / seed-invalidating `minimum_ap_version`) is MINOR pre-1.0; anything
   that preserves every contract — even if it changes generated output — is PATCH.
2. Update `world_version` and `package.json` (+ `package-lock.json`) to match.
3. Add a `CHANGELOG.md` entry.
4. Commit, tag `vX.Y.Z`, push commits and tags.
