# Sokopelago

A [Sokoban](https://en.wikipedia.org/wiki/Sokoban) implementation for the
[Archipelago](https://archipelago.gg) multiworld randomizer. Solve Sokoban levels to
send items to other players; receive items that unlock more levels and abilities.

See **[ROADMAP.md](ROADMAP.md)** for the authoritative scope and phase sequencing, and
**[VERSIONING.md](VERSIONING.md)** for the release/versioning policy (the project is in
beta — see **[CHANGELOG.md](CHANGELOG.md)**).

## Repository layout

```
apworld/     Python — the Archipelago world (items, locations, regions, rules, slot_data)
client/      TypeScript + Vite — the browser Sokoban game (the bulk of the work)
levels/      Canonical level corpus (XSB), shared by the client now and the apworld later
ROADMAP.md   Source of truth for scope + phasing
```

## Current status: Phase 5 done (`0.4.1`)

Phases 0–5 are shipped and CI-green: local Sokoban play, the apworld core (region-key
logic, solve-checks, goals), the live AP protocol client, Phase 3 escape valves
(skip/undo/hint tokens + traps), Phase 4 per-level par checks, and the Phase 5 expert
ability-logic tier — a **Pull** ability (opt-in Expert Logic) that hard-gates the
pull-required levels of the original **Pullban** corpus. Remaining roadmap work:
**Phase 6** (polish — PopTracker, more abilities/corpora, hosting/UX).

## Development

Run the game locally with the helper scripts at the repo root:

```sh
./dev.sh        # solo free-play: opens the client in your browser (no server)
./playtest.sh   # AP-connected: generates a 1-player seed, runs a local MultiServer,
                # and opens the client so you can test received items, world keys, and
                # the Hint / Skip / Undo tokens end to end
```

`./playtest.sh [yaml]` defaults to [`examples/Sokopelago-Local.yaml`](examples/Sokopelago-Local.yaml).
It needs a local Archipelago 0.6.7 checkout: set `AP_ROOT` to point at it (default: a
sibling `../Archipelago`) and `AP_PYTHON` to a Python that has Archipelago's deps
(e.g. `AP_PYTHON="mamba run -n archipelago python"`). Connect the client at
`localhost:38281` with the slot name printed by the script.

Tests and checks live in `client/`:

```sh
cd client
npm install
npm test          # parser + game-model + AP-session unit tests (Vitest)
npm run lint      # eslint  (also: npm run typecheck, npm run format:check)
```

### Branching & releases

Day-to-day work lands on **`dev`** (the default branch): commit small changes directly,
or branch `feature/<x>` off `dev` and PR back into it. CI runs on every push and PR.
`main` is release-only — pushing to it auto-deploys the client to GitHub Pages, so it
never carries WIP.

To cut a release, merge `dev → main`, then on `main` bump `world_version`
(`apworld/sokopelago/archipelago.json`) and `client/package.json` in lockstep, add a
[CHANGELOG.md](CHANGELOG.md) entry, commit, and push a `vX.Y.Z` tag (which publishes the
`.apworld`). See [VERSIONING.md](VERSIONING.md).

## Play (multiworld)

The web client is served on **GitHub Pages** and the world ships as an **.apworld** on
**Releases**. To play a seed:

1. **Install the world:** download `sokopelago.apworld` from the
   [latest release](../../releases/latest), then in the Archipelago launcher click
   **Install APWorld** (or drag the file onto it).
2. **Generate a seed** locally with a YAML (`corpus: microban` or `pullban`;
   `expert_logic: true` enables the Pull tier). Custom worlds must be generated locally —
   archipelago.gg can't generate them.
3. **Host it:** upload the generated output to
   [archipelago.gg → Host Game](https://archipelago.gg). (You need a `wss` room, which
   archipelago.gg provides — the hosted HTTPS client can't reach a plain `ws://` local
   server. To play against a *local* `MultiServer`, use `./playtest.sh` instead.)
4. **Connect:** open the Pages URL, enter the room's `host:port` and your slot name.

## Level corpora

- `levels/microban.xsb` — **Microban** by David W. Skinner (155 puzzles). Skinner's sets
  "may be freely distributed provided they remain properly credited" — see
  [`levels/ATTRIBUTION.md`](levels/ATTRIBUTION.md).
- `levels/pullban.xsb` — an original expert corpus (Pull-required levels) for the Phase 5
  ability tier. See [`CREDITS.md`](CREDITS.md).

## Archipelago integration (Phase 1+)

The apworld is bridged into a vanilla Archipelago clone via a symlink — Sokopelago is
not vendored inside any AP fork. See `apworld/README.md`.
