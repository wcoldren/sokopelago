# Release 0.7 — Accurate logic (alpha)

**Theme:** turn the flat region-key spine into real multiworld logic, and relabel the
project from beta to **alpha** to match. This is the release that makes Sokopelago a
*real* rando you can sync with friends.

**Bump:** MINOR → `0.7.0` (changes generation output + slot_data + client; per
`VERSIONING.md` a patch can't touch generation or the datapackage). The logic work adds
**no new location/item IDs**, so the datapackage stays stable.

## In scope — and nothing else
- Boss-zone gate, count-floor body chaining, Pull-**item** late placement.
- Tunable knobs for the above, plus a sweet-spot pass on default level count / region size.
- The beta → alpha relabel + the version bump.
- Bug fixes that surface while doing the above.

## Out of scope (defer; none of these block 0.7)
Larger pull corpus, new abilities (push-two, ice, …), campaign mode, the Adventure
overworld, more corpora, hidden-goal levels.

---

## 1 — apworld logic (`apworld/sokopelago/`)

- [ ] **Boss gate.** In `create_regions`, gate the final world (`i == region_count`) on
      `state.has_all(all_keys)` (keys for worlds 2..N) instead of its own single key.
      Mirror it in `set_rules`: `beat_final_region` completion → `has_all(all_keys)`
      (the existing `_completion` wrapper still ANDs in Pull when pull levels exist).
      Keep `solve_count` / `boss_level` experimental — their key-counting changes under
      the deeper gate. See `docs/DESIGN-boss-zone.md`.

- [ ] **Count-floor chaining.** Add a pure `floor_schedule(region_count, group, cap)` to
      `layout.py` (no AP imports, unit-tested like its neighbours):
      - World 1 → `0` (free).
      - Body world `i` (2..N-1) → `floor_i = min((i - 2) // group, region_count - 2)`.
      - Boss world N → `region_count - 1` (all keys).

      In `create_regions`, body-world access becomes
      `has(World i Key) AND has_from_list(all_keys, floor_i)`. (The floor counts *all*
      held keys incl. the world's own, so min keys to enter = `max(1, floor_i)`.)
      **Fillability invariant the schedule must preserve:**
      `floor_i ≤ (number of keyed worlds strictly easier than i)` — satisfied because
      `(i-2)//group ≤ i-2` for `group ≥ 1`. Don't ship a schedule that breaks it.

- [ ] **Pull-item late placement.** When `pull_logic` is on and the seed has pull levels,
      forbid the Pull **item** from early locations via `add_item_rule` on worlds below a
      key-count floor, so Pull can only be *acquired* in a late sphere (it removes
      irreversibility, which trivialises early push puzzles). Pull **levels** stay
      placeable anywhere — they're gated by the existing `_apply_pull_gate` access rule, so
      you get the "come back once you have Pull" backtracking (e.g. a key behind a Pull
      level in World 1). Decouple "requires_pull" from difficulty in any wording/comments —
      it is **not** a synonym for "expert/hard".

- [ ] **Knobs.** Add `chain_group` (controls body steepness; lower = steeper). Default to a
      light-but-active value for 0.7; `group` large enough to flatten back toward the old
      star is the back-compat escape hatch. The **boss gate is correctness, not optional.**
      New options carry no name→id, so the datapackage is unaffected.

## 2 — slot_data + client mirror

- [ ] In `fill_slot_data`, ship the per-world floors (or the schedule params to recompute)
      and a boss-world / all-keys flag.
- [ ] Mirror the gate in `client/src/ap/session.ts` (`isLevelUnlocked` / `unlockedWorlds`):
      a world unlocks when its own key is held **and** total keys ≥ `floor_i`; the boss
      world unlocks only on all keys. The client gate must match server logic exactly or
      players desync from their own seed.

## 3 — tests (`apworld/sokopelago/test/`)

- [ ] Boss world reachable only with all keys; the seed is **not completable** before all
      keys are held (no early win) for `beat_final_region`.
- [ ] Chaining is fillable across world counts, including edge cases: `levels_per_region = 1`
      (many tiny worlds) and very small pools.
- [ ] The Pull item is never placed before its floor sphere.
- [ ] Update `test_filler` / `test_goals` / `test_world` / `test_layout` for the new rules.

## 4 — sweet-spot tuning

- [ ] Use `tools/preview_layout.py` to settle defaults for `level_count`,
      `levels_per_region`, and `chain_group` that feel right (low group steepens the body).
      Ship those as defaults; iterate on friend feedback rather than guessing now.

## 5 — relabel + release (`VERSIONING.md` checklist)

- [ ] beta → **alpha** across README / `VERSIONING.md` / `CHANGELOG.md` (label only — the
      version number keeps climbing; do not renumber backward).
- [ ] Fix the stale `VERSIONING.md` line: "Current version: 0.4.0" → `0.7.0`.
- [ ] Bump `world_version` (`archipelago.json`) and `client/package.json` (+ lockfile) to
      `0.7.0`.
- [ ] Add the `CHANGELOG.md` entry; commit; tag `v0.7.0`.

---

## Decisions resolved during planning (2026-06-21)

These refine the spec above; where they differ, **these win** (the code follows them):

1. **Default `levels_per_region` → 5** (was 10). With `level_count = 30` that yields **6
   worlds**, so count-floor chaining is light-but-active out of the box (at 3 worlds it was
   inert). `chain_group` default is **2**.

2. **The new access rules are scoped to `goal = beat_final_region`.** Both the boss
   all-keys gate *and* the body count-floors apply only under `beat_final_region`.
   `solve_count` and `boss_level` keep the **untouched 0.6 single-key-per-world layout**
   (their key-counting helper, `solve_count_keys_needed`, assumes single-key access;
   chaining would invalidate it) and stay labeled **experimental** — so there is zero
   regression in those goals. This is the conservative reading of "keep solve_count /
   boss_level experimental."

3. **Pull-item floor is conservative with a fallback.** `pull_floor = max(1,
   (region_count-1)//2)`. A solve location is Pull-eligible iff it is in a body world at or
   above that floor, is **not** the boss world, and is **not** itself pull-gated. If no
   eligible host exists, the floor is **disabled** (Pull places anywhere reachable, as in
   0.6) rather than risk an unfillable seed. "requires_pull" (a level-access gate) is
   decoupled in code/comments from the Pull-item placement floor. **Note:** with the shipped
   10-level pullban corpus (60% pull-gated) the floor stays in its disabled fallback (no
   eligible late host) — it is implemented and safe but **dormant** until the corpus is
   augmented. See `docs/DESIGN-pull-corpus.md` (planned `0.8.0` follow-up) for the corpus fix
   that activates it and makes pull seeds robustly fillable at all region sizes.

4. **`tools/preview_layout.py` will be built** (minimal, pure, no AP imports) for the
   section-4 tuning — it does not exist yet.

5. **Client mirror ships resolved data, not params.** `fill_slot_data` ships
   `chain_floors` (per-world resolved floor; all `0` when the goal isn't `beat_final_region`)
   and `boss_all_keys` (bool). The client recomputes its unlocked set from the held-key
   count each sync, so it matches the server for **every** goal and can't drift from a
   re-derived formula.
