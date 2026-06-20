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

## Current status: beta (`0.x`)

We are pre-1.0. Per SemVer, the `0.x` line carries no stability promise — the public API,
`slot_data` schema, and ID layout may still move. Current version: **`0.3.0`**.

The minor digit bumps on each world/datapackage-affecting change, **not** per roadmap
phase number. History to date: `0.1.0` (Phase 1, world core) → `0.2.0` (Phase 3 valves)
→ `0.3.0` (Phase 4 par checks). Phase 2 was a client-only integration milestone and rode
along with no world bump.

### While `< 1.0.0`

- **MINOR** (`0.4 → 0.5`): a completed roadmap phase, new options/items/locations, or
  any change to seed compatibility, `slot_data` schema, or location/item ID assignments.
  (Under SemVer, breaking changes ride minor bumps while `< 1.0`.)
- **PATCH** (`0.4.0 → 0.4.1`): bug fixes, client-only fixes, docs, tests — nothing that
  alters generation output or the datapackage.

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

1. Decide the bump (major/minor/patch) using the rules above.
2. Update `world_version` and `package.json` (+ `package-lock.json`) to match.
3. Add a `CHANGELOG.md` entry.
4. Commit, tag `vX.Y.Z`, push commits and tags.
