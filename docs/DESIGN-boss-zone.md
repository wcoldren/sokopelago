# Design: boss zone — make the final world reachable last

Status: **proposal, not yet built.** Captures the progression/sphere-ordering problem found
during 0.6 playtesting. No code changes accompany this doc beyond a pointer comment at the
key-gating site. Build behind the existing options and bump `world_version` when shipped (it
changes logic + slot_data + the client gate — see [VERSIONING.md](../VERSIONING.md)).

## The problem

World keys are ordinary **progression items placed freely by AP fill**. Each keyed world is
gated on a *single* key:

```python
# apworld/sokopelago/__init__.py  (create_regions)
menu.connect(region, f"Menu -> World {i}",
             rule=lambda state, key=key: state.has(key, self.player))
```

There is no chain, `item_rule`, `local_items`, or multi-key access rule (`create_items`,
`set_rules`). So the **World N (final) key can be placed anywhere — including World 1 — and
found first.** With the default `beat_final_region` goal, the client win is "every level in the
final world is solved" (`client/src/ap/slotData.ts::isGoalMet`), so a player who draws the
final key early can open the final world and clear it **while skipping worlds 2..N-1** — beating
the seed in the first sphere and trivializing the difficulty ramp. (The 0.6 beta ships with a
disclaimer covering this; it is not yet safe for real syncs/asyncs.)

## Goal

The final ("boss") zone should be reachable **only after** the other worlds. The player roams
worlds 1..N-1 in any order; the boss zone unlocks last, no matter when its key is found.

## Recommended approach: boss world gated on all other keys

Gate the boss world's Menu access on **all** other world keys (AND of World 2..N keys), rather
than just its own:

```python
# create_regions: for the final world i == region_count
all_keys = [world_key_name(k) for k in range(2, self.region_count + 1)]
menu.connect(region, f"Menu -> Boss Zone",
             rule=lambda state: state.has_all(all_keys, self.player))
```

- The boss key can be found at any time, but the boss zone is always the **deepest sphere**
  (needs every other key), so it is entered last. Fill keeps it solvable because the boss key
  must land in a non-boss location (the boss world is unreachable until all keys are held).
- **Mirror it client-side**: `Session.isLevelUnlocked` / `unlockedWorlds`
  (`client/src/ap/session.ts`) must require *all* keys for boss-world levels, so the client gate
  agrees with server logic (today the client unlocks a world as soon as its single key arrives).
  This likely means sending the boss-world index (or an "all keys" flag) in slot_data.
- Optional flavor: rename World N → **"Boss Zone"** and its key → **"Boss Key"**.

## Alternatives considered

- **Linear key chain** (World k+1 reachable only from World k): simplest spheres, but removes the
  "roam the other worlds freely" feel the design wants.
- **Per-item placement depth rules**: fragile and easy to make unfillable.

## Caveats / scope

- Clean for `beat_final_region`. `solve_count` and `boss_level` need their own thought (the boss
  world's deeper gate changes key-counting / reachability) — keep them experimental until then.
- Touches the apworld access rules + completion, slot_data, the client unlock logic, and tests;
  it is a `world_version`-bumping logic release of its own, not a 0.6 patch.
