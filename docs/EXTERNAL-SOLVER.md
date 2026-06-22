# External solver (SokoBoy) — setup & usage

## Why this exists

`tools/solve_corpus.py` is a pure-Python, push-**optimal** Sokoban solver. It cracks the entire
Microban set bar one level, but two situations exceed it:

- **A few individually hard levels** — e.g. Microban **153** (a 10-box comb) resists every
  pure-Python configuration (weights 1.0–5.0, greedy, 600 s+ / 40M-node budgets).
- **Expert-scale corpora** — e.g. the ingested **XSokoban 90** set has a median of ~15 boxes and
  goes up to **34** boxes per level; optimal push-solving at that scale is far beyond the in-house
  A*, so almost every level times out.

For these, `solve_corpus.py` has a **data-prep-only** escape hatch: the `SOKO_SOLVER_CMD` hook
(`_external_solve`, `tools/solve_corpus.py`). It is **never on the generation path** and never a
runtime dependency — it only runs offline when you set the env var. Whatever the external process
returns is **replay-verified** (`solve_corpus.replay`) exactly like a native solution before it is
trusted, and the resulting manifest entry is flagged `"solver": "external"` (`"optimal": false`).

The external solver itself is **never vendored or committed** — it is built locally and pointed to
via an env var. Only *our* glue (`tools/sokoboy_solve.py`) and this doc live in the repo.

## The solver: SokoBoy

[SokoBoy](https://github.com/celicom11/SokoBoy) by celicom11 — an open-source C++17 console Sokoban
solver (BFS/DFS/AStar), no external dependencies. We use **AStar** (sub-optimal but tractable on
hard/large levels; BFS is optimal but blows up). License: see the SokoBoy repo (run locally only;
not redistributed).

### Build on macOS (clang)

SokoBoy targets MSVC; a small compatibility shim makes it build with `clang++ -std=c++17`. Clone
into the gitignored `.sokoboy/` and apply these (all recorded so the build is reproducible):

1. **Compat header** `.sokoboy/_compat.h`, force-included via `-include _compat.h`. For non-`_WIN32`
   it defines `_ASSERT`→`assert`, empties `__declspec(x)` and `abstract`, defines `_countof`,
   `_MAX_PATH`→`PATH_MAX`, and makes the Windows console calls `_setmode`/`_fileno`/`_O_U16TEXT`
   no-ops (the LURD solution is written to a *narrow* `ofstream`, so console wide-mode is irrelevant).
2. **`StdAfx.h`** — guard the Windows-only includes: wrap `#include <io.h>` / `#include <fcntl.h>` in
   `#if defined(_WIN32) … #endif`.
3. **`Reporter.cpp`** is UTF-16 LE — clang can't read it. Convert to UTF-8:
   `iconv -f UTF-16LE -t UTF-8 Reporter.cpp > tmp && mv -f tmp Reporter.cpp`.

Then compile (top-level `*.cpp` only — the `UnitTests/` subdir is excluded):

```sh
cd .sokoboy
clang++ -std=c++17 -O2 -include _compat.h *.cpp -o sokoboy
```

The portable bit-ops (`_BitScanForward64`/`__popcnt64`) and the `_ReadAllFiles` globber already have
non-Windows fallbacks in the source, so nothing else is needed.

### SokoBoy's native interface (why a wrapper is required)

SokoBoy does **not** take a level path on argv or print to stdout. It reads a **`Sokoboy.cfg`** from
its working directory and **writes the solution to a file** `{puzzle-stem}_{Search}.txt` next to the
puzzle. Relevant config keys (`Key=Value`, `;` comments):

```
PuzzlePath=/abs/path/to/level.xsb   ; must be directory-qualified (it globs parent_path())
Search=AStar                        ; BFS|DFS|AStar
RSM_Depth=1                         ; reverse-pull-tree depth; 1 is the recommended default
Rpt_Sol=2                           ; 2 = emit the LURD string (1 = XSB stages, 3 = both)
Rpt_SQInc=0                         ; progress reporting off
```

The output file contains a header and the move string, e.g.:

```
Approximate LURD:
LuRdldRdrruuLLdlUruulldDrddlluR
```

The LURD uses **uppercase L/U/R/D for pushes and lowercase for the connecting walks** — exactly the
move-string format `solve_corpus.replay` and the `_LURD_RUN` extractor expect.

## The bridge wrapper: `tools/sokoboy_solve.py`

`solve_corpus._external_solve` expects a command that takes the level path and prints LURD to
**stdout**. `tools/sokoboy_solve.py` adapts SokoBoy to that contract: it writes a one-shot
`Sokoboy.cfg` next to the level, runs the SokoBoy binary (`$SOKOBOY_BIN`), and echoes the
`*_AStar.txt` solution file to stdout (from which `_external_solve` extracts and replay-verifies the
LURD). It honors `SOKO_SOLVER_TIMEOUT` and is a no-op (exit 2) if `SOKOBOY_BIN` is unset.

## Usage

```sh
# from the repo root; both paths must be ABSOLUTE (the hook runs the command with cwd=<tempdir>):
export SOKOBOY_BIN="$PWD/.sokoboy/sokoboy"
export SOKO_SOLVER_CMD="python $PWD/tools/sokoboy_solve.py {level}"
export SOKO_SOLVER_TIMEOUT=600        # seconds per level (default 300)

# annotate an expert corpus (capped internal solve falls back to SokoBoy on failure):
python tools/annotate_corpus.py --corpus xsokoban90 --workers 8

# or (re)solve a hand-authored corpus end-to-end:
python tools/solve_corpus.py --corpus <name>
```

Notes / gotchas:
- **Absolute paths are required** in `SOKO_SOLVER_CMD` and `SOKOBOY_BIN` — `_external_solve` runs the
  command from a temp directory, so a relative `tools/...` path won't resolve.
- `{level}` in `SOKO_SOLVER_CMD` is replaced with the temp `.xsb` path; if omitted, the path is
  appended.
- Expert levels can still time out per level — coverage is **reported, not assumed**. Set
  `SOKO_SOLVER_TIMEOUT` to taste; levels that don't solve stay honestly `solved=false`.

## Acceptance test (Microban 153)

The canonical end-to-end check — Microban 153 is solvable *only* via the external solver:

```sh
SOKOBOY_BIN="$PWD/.sokoboy/sokoboy" SOKO_SOLVER_CMD="python $PWD/tools/sokoboy_solve.py {level}" \
  SOKO_SOLVER_TIMEOUT=600 python tools/solve_corpus.py --corpus microban   # level 153 -> solver=external
```

SokoBoy solves it with AStar (~4 min) into a ~330-push LURD that `replay` confirms — proving the
binary + wrapper + contract are wired correctly.
