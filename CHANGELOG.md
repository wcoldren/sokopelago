# Changelog

All notable changes to Sokopelago are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to the policy in
[VERSIONING.md](VERSIONING.md). The project is in alpha (`0.x`); the version is the
apworld `world_version`, with the client kept in lockstep. The minor digit bumps on
contract changes (datapackage / `slot_data` schema / option schema), not roadmap phase
numbers and not on every change to generated output.

## [0.7.0] — Accurate logic: boss-zone gate + count-floor chaining

Turns the flat region-key spine into real multiworld logic, so a seed can no longer be beaten
out of order. The project label moves from beta to **alpha** to match. No new location/item IDs
(the datapackage is unchanged); `slot_data` gains two fields, which is why this is a minor bump.

### Added
- **Boss-zone gate** (`beat_final_region`): the final world now unlocks only once **every** other
  world key is held, so it is always the deepest sphere. This closes the 0.6 hole where the final
  world's key could be found first and the seed beaten while skipping the middle worlds
  (`docs/DESIGN-boss-zone.md`).
- **Count-floor chaining**: body worlds open behind their own key **plus** a floor of earlier keys
  (`has_from_list`), so progress fans out instead of every world opening the instant its lone key
  appears. New **`Chain Group`** option tunes the steepness (lower = steeper; a large value
  flattens back to the classic single-key star). The effective chain depth is bounded for fill
  robustness (a pure `effective_floor_schedule` in `layout.py`).
- **Expanded `pullban` expert corpus**: 10 → **30 levels** (pull-gated fraction 60% → 30%), all
  offline-solver-verified. The extra push-solvable hosts make expert (Pull Logic) seeds fill
  reliably (was 5–100% failures at small region sizes → now ~0). See `docs/DESIGN-pull-corpus.md`.
- **`tools/preview_layout.py`**: prints a seed's world layout + per-world key-count floors for a
  given option set (a pure tuning aid).
- `slot_data` now ships `chain_floors` (resolved per-world floors) and `boss_all_keys`; the browser
  client mirrors the gate exactly so the unlock UI matches server logic for every goal.
- **World-grouped level picker** (client): the dropdown is replaced by a grid of world cards with
  level "pills". Each world header shows its difficulty range and key/lock state, and the **boss
  world spells out "needs ALL keys (held/total)"** so the gate is explicit.

### Changed
- **Default `Levels Per Region` is now 5** (was 10), so a default seed has more worlds and the
  count-floor chain is active out of the box.
- **Per-world level numbering** (client): levels read `World N · L{pos}` (sequential within a
  world) instead of the raw Microban corpus number, which jumped around under shuffled selection;
  the corpus number is kept as the pill tooltip / title detail.
- **World-aware "next"** (client): after a solve the game advances within the current world, then
  to the next *unlocked* world, only wrapping back when everything ahead is locked.
- **beta → alpha** label across the README, client, and docs; the versioning policy is now
  contract-based (see `VERSIONING.md`).

### Notes
- `solve_count` / `boss_level` keep the 0.6 single-key-per-world layout and remain experimental;
  the boss-zone gate and chaining apply to `beat_final_region` only.

## [0.6.0] — Easy-first release: honest difficulty, tier gating, gentle first world, play stats

### Changed
- **Difficulty is now an honest, absolute score.** The per-level `difficulty` is a log-scaled
  blend of par / search-nodes / moves / boxes (`tools/solve_corpus.py`), so "easy" means a
  genuinely simple puzzle instead of "the bottom third". This fixes the prior bug where one
  outlier (Microban 153) min-max-pinned the scale and made nearly every level read as easy. The
  microban split is now ~41 easy / 104 medium / 10 hard. Tier cutoffs (`easy < 0.33`,
  `hard >= 0.66`) are centralized in `apworld/sokopelago/tiers.py` and mirrored by the client
  badge. Difficulty values feed seed selection/ordering, so the same seed name may compose
  differently — hence the world-version bump.
- **0.6 defaults to easy-only seeds.** The new `max_difficulty` option defaults to `easy`, so the
  AP-generated template and any YAML that omits it produce a gentle, easy-tier seed. Raise it to
  `easy_medium` or `any` for tougher puzzles. The bundled `Sokopelago-Tiers`/`Sokopelago-Local`
  examples pin `max_difficulty: any` to keep their full-range behaviour.

### Added
- **`max_difficulty`** (`any` / `easy` / `easy_medium`): caps a seed's level pool to a tier
  ceiling, filtered before selection so `level_count` draws from (and clamps to) the eligible pool.
- **`gentle_first_world`** (on by default): keeps World 1 ("sphere 1") to easy-tier puzzles for a
  gentle start, even when the rest of the seed spans harder tiers. No-op for an all-easy seed.
- **Per-level play stats**: visits, unique visits (distinct play sessions), and a per-solve event
  log (moves / pushes / time, with derived bests), recorded in both solo (localStorage) and
  AP-connected (DataStorage) play and shown in the HUD. **Export/Import** buttons serialize the
  stats as JSON for offline cross-player analysis. See [`docs/DESIGN-statistics.md`](docs/DESIGN-statistics.md).
- **`examples/Sokopelago-Easy.yaml`** — the easy-first single-player config (mirrors the default).
- **In-client goal line** — the win condition is shown in plain language (e.g. "solve every level
  in the final world") instead of only a raw enum in the connection status.
- **Beta disclaimer** in the client and README: solo + basic multiworlds work, but it's not yet
  recommended for real syncs/asyncs while sphere ordering is refined.
- **`docs/DESIGN-boss-zone.md`** (deferred): the final world's key can currently be found first;
  documents gating the boss zone behind all other keys. `beat_final_region` is the tested goal for
  0.6; `solve_count`/`boss_level` are experimental.

### Fixed
- The perfect (★) vs efficient (✦) HUD message now spells out how far over optimal an efficient
  solve was, so ✦ isn't mistaken for ★. Replaying a solved level in fewer pushes now **upgrades**
  its tier (sends the newly-earned par/efficiency check) instead of being ignored.
- **★/✦ "doing well" markers now show in multiworld**, derived client-side from your best pushes
  vs the level's optimal (plus a default margin), so they appear in solo and AP alike even when the
  seed has no par checks. The AP par/efficiency reward checks remain opt-in.

## [0.5.0] — Seed-varied selection + tiered par

### Added
- **Seed-varied puzzle selection** (`level_selection` option): the new `shuffled_buckets`
  mode draws a different subset of corpus levels per seed. Levels are grouped into
  `difficulty_buckets` tiers, shuffled within each tier using the multiworld's seeded RNG,
  and a size-proportional share is taken — so different seeds play different puzzles while
  the easy→hard ramp is preserved. Default is `native` (the previous deterministic
  first-N-levels behaviour), so existing YAMLs are unchanged.
- **Tiered par checks**: a new **efficient** tier on top of the existing **perfect** tier.
  `efficiency_checks` adds a third location per level ("Solve Microban n efficiently") that
  sends when a level is solved within `efficiency_margin` percent over the optimal push
  count — a gettable reward, where the par-checks location still demands exactly optimal.
  Efficient locations are filler-only (`EXCLUDED`); the tier requires Par Checks to be on.
- slot_data gains `efficiency_checks` and `efficiency_margin`; a new efficiency location
  band (`9_780_000 + n`) is added (additive — published solve/par IDs are unchanged, so
  older seeds stay valid).

### Changed
- **Difficulty re-scored**: the offline solver now persists `search_nodes` (search
  effort / branching) instead of discarding it, and the composite `difficulty` is
  re-weighted toward par and branching (par .40 / nodes .35 / moves .15 / boxes .10).
  Corpus manifests regenerated; pars, solutions, and boards are unchanged.
- The `boss_level` goal now resolves to the **nearest selected level** when the requested
  number isn't drawn (possible under `shuffled_buckets`); `0` means the seed's
  highest-numbered level.

## [0.4.1] — Solo-play hints

### Fixed
- The **Hint** button now works in solo play (no AP connection): it reveals the next
  solution move for free, mirroring how **Undo** already behaves offline. Previously the
  button was hidden and `useHint()` no-opped without a connected session, since Hint
  Tokens only exist as multiworld items. When connected, Hint still consumes a token.
  Client-only change; no datapackage/generation impact.

## [0.4.0] — Phase 5: expert ability-logic tier (Pull)

### Added
- **Pull ability** end-to-end: the offline solver gained a pull-aware mode that proves
  which levels are unsolvable by pushing alone, the client implements the pull mechanic
  (Shift+direction, or a Pull-mode toggle), and a **Pull** progression item hard-gates
  those levels under a new **Expert Logic** option (default off).
- **Pullban** — an original expert corpus (`levels/pullban.xsb`): a mix of push-solvable
  hosts and pull-required levels, selectable via the `corpus` option (`pullban`).
- Multi-corpus support: per-corpus manifests (`data/<corpus>.json`) with bundled boards;
  the client loads the seed's corpus on connect; build tools take `--corpus`.
- slot_data gains `corpus`, `expert_logic`, and `requires_pull`.

## [0.3.0] — Phase 4: check density

### Added
- Per-level **par checks**: a second location `Solve Microban N in <= par pushes`, gated
  behind the new `par_checks` option (default off). Par locations are filler-only
  (`EXCLUDED`) so a par requirement can never strand progression.
- Par targets shipped in `slot_data`; client reports the par check when a level is solved
  at or under par, with under-par/missed feedback in the UI.

## [0.2.0] — Phase 3: filler + escape valves

### Added
- Escape valves as useful items: **Skip Token**, **Undo Charge**, **Hint Token**.
- **Trap** items (Scramble, Decoy Box, Reversed Controls) via the `trap_percentage` option.
- Intra-region difficulty flattening (`difficulty_ordering`) so non-linear key order
  doesn't drop a player onto a brutal world first.
- Offline solver upgrade → 155/155 replay-verified solutions + push par + difficulty in
  the bundled manifest; client hint playback; Skinner attribution/credit.

## [0.1.0] — Phase 1 (apworld core) + Phase 2 (AP protocol client)

### Added
- Item table (region keys), location table (one `Solve <level>` per level), region graph
  gated by keys, `set_rules` region-access logic, core options, and `fill_slot_data` —
  the apworld is provably beatable.
- AP protocol client built on `archipelago.js`: websocket handshake, `ReceivedItems` →
  region/level unlocks, `LocationChecks` on solve, `StatusUpdate` GOAL, DataStorage-backed
  progress/reconnect — verified end-to-end against a live `MultiServer.py`. (Client-only
  integration milestone; rode along with no separate `world_version` bump.)

## [0.0.x] — Phase 0: scaffolding + corpus

### Added
- Repo skeleton (`apworld/`, `client/`), XSB parser, board rendering, base Sokoban
  (move/push/win), and the Microban corpus — playable locally with no AP connection.

[0.4.0]: https://github.com/wcoldren/sokopelago/releases/tag/v0.4.0
[0.3.0]: https://github.com/wcoldren/sokopelago/releases/tag/v0.3.0
