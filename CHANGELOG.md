# Changelog

All notable changes to Sokopelago are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to the policy in
[VERSIONING.md](VERSIONING.md). The project is in beta (`0.x`); the version is the
apworld `world_version`, with the client kept in lockstep. Versions correspond to
world/datapackage-affecting changes, not roadmap phase numbers.

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
