# Sokopelago — Roadmap

A Sokoban implementation for the [Archipelago](https://archipelago.gg) multiworld randomizer.
Solve Sokoban levels to send items to other players; receive items that unlock more levels and abilities.

This doc is the source of truth for scope and sequencing. Read it before starting work.

---

## What this is

Two pieces plus one optional tool:

1. **apworld (Python)** — defines items, locations, regions, logic rules, options, and slot_data. Lives in / built against `ArchipelagoMW/Archipelago`. This is the easy part.
2. **Web client (JS, browser)** — the actual Sokoban game. Connects to the Archipelago server over websocket, receives items, sends location checks when levels are solved. This is the bulk of the work.
3. **Offline solver (Python, optional)** — run once during data-prep. Verifies the level corpus is solvable, computes "par" push counts, and (later) tags each level's minimal mechanic set for the expert logic tier. Never runs at generation time.

**Hard constraint:** the generator must never solve Sokoban. Sokoban solving is expensive; all solvability facts are precomputed offline into a static data table that both the apworld and client consume.

---

## Gating design (the core decision)

Two gating axes, treated differently:

### Level access = the hard logic spine
- Levels are grouped into **regions** ("worlds").
- Each region is opened by a **key item** (`World 2 Key`, etc.).
- Levels are **locations** inside their region.
- Keys are shuffled into the multiworld, so key order is non-linear — you might open World 3 before World 1 and solve whatever's reachable.
- `rules.py` is trivial: a location is reachable iff its region key is held. Standard region-access logic.

### Mechanic abilities = soft difficulty layer (default), optional hard gate (expert)
Abilities like **pull**, **push-two**, **diagonal move**, **teleport charges**, **undo** are *naturally soft* — they make levels easier, not reachable-vs-not.

- **Default logic:** abilities are optional helpers, off the critical path.
- **Expert logic (later phase):** the offline solver annotates each level with the minimal mechanic set required to solve it (solver-with-pull finds a solution, solver-without finds none → level is hard-gated behind Pull). Those annotations promote specific abilities to hard requirements for specific levels. Still just a lookup table at generation time.

---

## Key risk: AP logic ≠ player skill

Archipelago logic reasons about **item** reachability, not whether you can actually solve a reachable level. A skill wall stalls your slot and everyone waiting on checks behind it. This is not fixed in logic — it's fixed with escape valves:

- **Skip tokens** in the pool (consume to bypass a stuck level).
- **Hint items** (reveal next push / show a solution).
- **Flatten difficulty within the access structure** so non-linear key order doesn't drop a player onto a brutal world first.

Treat these as required for v1, not polish.

---

## Phases

### Phase 0 — Scaffolding + corpus (local-only, no AP yet)
- Repo skeleton: `apworld/` (Python) and `client/` (JS).
- Import a level corpus in **XSB format** (Microban is the standard community choice — small levels, good ramp, widely treated as freely distributable; **confirm license**).
- XSB parser in the client.
- Render a board; implement base Sokoban (move, push one box, win detection); play levels locally.
- **Milestone:** you can play the corpus in a browser with no AP connection.

### Phase 1 — apworld core
- Item table: region keys (progression).
- Location table: one location per level (`Solve <level>`).
- Region graph: worlds gated by keys, levels as locations inside.
- `set_rules`: location reachable iff region key held.
- Minimal options: corpus selection, number of levels, goal type.
- `fill_slot_data`: which levels are in the seed, region→level map, goal.
- **Milestone:** a multiworld seed generates and is provably beatable.

### Phase 2 — AP protocol client (the integration milestone)
- Websocket connect + handshake (`Connect` → `Connected` with slot_data).
- Handle `ReceivedItems` → unlock regions/levels.
- Send `LocationChecks` when a level is solved.
- `StatusUpdate` GOAL on completion.
- DataStorage (`Set`/`Get`) for progress persistence + clean reconnection.
- **Do not** reconstruct the protocol from memory — read `docs/network protocol.md` in the Archipelago repo and crib the client wiring from an existing open-source web game (ChecksFinder, Jigsaw, or Sudoku).
- **Milestone:** end-to-end — solve a level, another slot receives the item; receive a key, a new world opens.

### Phase 3 — Filler + escape valves
- Skip tokens, hint items, undo charges as filler/useful items.
- Flatten intra-region difficulty.
- Optional: trap items (scramble level, decoy box, reversed controls for one level).

### Phase 4 — Check density
- Add a second location per level: `Solve <level> in ≤ par pushes`.
- Requires the offline solver to compute par. Roughly doubles check count; turns mastery into multiworld events instead of dead time.

### Phase 5 — Expert ability-logic tier ✅ (shipped 2026-06-20, `0.4.0`)
- Offline solver tags per-level minimal mechanic requirements.
- Ability items (Pull, Push-Two, …) as hard gates under an opt-in logic-difficulty option.
- Client implements the corresponding mechanics.
- **As shipped:** the **Pull** ability only, against an original **pullban** corpus whose
  harder levels are provably unsolvable by pushing (Microban is 100% push-solvable, so it
  can't gate anything). Opt-in via the `expert_logic` option; the solver proves each gate.
  Push-Two / diagonal / teleport remain future passes.

### Boss-zone sphere ordering (deferred from 0.6)
- The final world's key is placed freely, so it can be found first and the seed beaten before the
  middle worlds. Gate the final ("boss") world behind **all** other keys (server + client). Its
  own logic release. See [`docs/DESIGN-boss-zone.md`](docs/DESIGN-boss-zone.md).

### Phase 6 — Polish
- Tracker support (PopTracker).
- Broader options, multiple corpora, settings/UX.

**v1 ships Phases 0–2 only:** region-key logic, solve-checks, simple "beat the final region" goal, plus the Phase 3 escape valves. No abilities, no par checks, no solver.

---

## Open decisions
- Corpus + license confirmation (Microban vs others).
- Region size / count and difficulty distribution.
- Goal options: beat final region vs solve N vs designated boss level.
- Hosting for the web client.

## References
- Archipelago: `github.com/ArchipelagoMW/Archipelago` — `docs/network protocol.md`, `docs/world api.md`.
- Crib protocol client from: ChecksFinder, Jigsaw, or APSudoku (all open source web games).
- XSB level format; Microban by David W. Skinner.
