# Sokopelago

A [Sokoban](https://en.wikipedia.org/wiki/Sokoban) implementation for the
[Archipelago](https://archipelago.gg) multiworld randomizer. Solve Sokoban levels to
send items to other players; receive items that unlock more levels and abilities.

See **[ROADMAP.md](ROADMAP.md)** for the authoritative scope and phase sequencing.
**v1 ships Phases 0–2** (region-key logic, solve-checks, a simple goal, plus escape valves).

## Repository layout

```
apworld/     Python — the Archipelago world (items, locations, regions, rules, slot_data)
client/      TypeScript + Vite — the browser Sokoban game (the bulk of the work)
levels/      Canonical level corpus (XSB), shared by the client now and the apworld later
ROADMAP.md   Source of truth for scope + phasing
```

## Current status: Phase 0 — Scaffolding + Corpus (local-only, no AP yet)

The client plays the Microban corpus locally in a browser with no Archipelago
connection. The apworld is a stub until Phase 1.

## Client quickstart

```sh
cd client
npm install
npm run dev      # open the printed localhost URL and play
npm test         # parser + game-model unit tests (Vitest)
```

## Level corpus

`levels/microban.xsb` is **Microban** by David W. Skinner (155 puzzles). Skinner's sets
"may be freely distributed provided they remain properly credited" — see
[`levels/ATTRIBUTION.md`](levels/ATTRIBUTION.md).

## Archipelago integration (Phase 1+)

The apworld is bridged into a vanilla Archipelago clone via a symlink — Sokopelago is
not vendored inside any AP fork. See `apworld/README.md`.
