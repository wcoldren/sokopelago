# Credits

## Levels — Microban

The level corpus (`levels/microban.xsb`, 155 puzzles) is the **Microban** set by
**David W. Skinner**.

- **Author:** David W. Skinner
- **Set:** Microban (155 puzzles, revised April 2000)
- **Source:** <https://www.onlinespiele-sammlung.de/sokoban/sokobangames/skinner/>

Skinner releases his Sokoban level sets for free distribution on the condition that
they remain properly credited:

> These sets may be freely distributed provided they remain properly credited.

Sokopelago bundles the set unmodified (aside from a prepended attribution header that
is an XSB comment, ignored by every parser) so the credit travels with the corpus.
See [`levels/ATTRIBUTION.md`](levels/ATTRIBUTION.md) for the full distribution terms
and provenance.

The in-app credit is surfaced in the client footer (`client/index.html`).

## Solutions / par data

Per-level solutions and push-par values in `apworld/sokopelago/data/microban.json` are
computed offline by Sokopelago's own pure-Python solver (`tools/solve_corpus.py`); they
are not imported from any third-party solution set.

A small number of levels are beyond that pure-Python search. For those, the solver's
build-time `SOKO_SOLVER_CMD` hook can shell out to a developer-local external solver
(data-prep only — never on the generation path), whose output is replay-verified here
exactly like a native solution. Entries produced this way are flagged with
`"solver": "external"` in the manifest. The committed manifest's level 153 was solved
this way using [SokoBoy](https://github.com/celicom11/SokoBoy) (an open-source C++
console solver, run locally — not vendored or redistributed).
