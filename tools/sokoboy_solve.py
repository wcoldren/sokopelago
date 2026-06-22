#!/usr/bin/env python3
"""Bridge wrapper: adapt the external SokoBoy solver to ``solve_corpus``'s SOKO_SOLVER_CMD contract.

``tools/solve_corpus.py``'s external-solver hook (``_external_solve``) expects: receive a level's
``.xsb`` path as an argument and print a LURD move-string to **stdout** (which it regex-extracts and
replay-verifies). SokoBoy's native interface does neither — it reads a ``Sokoboy.cfg`` from its
working directory and writes the solution to ``<puzzle>_<Search>.txt``. This wrapper bridges the
two: it writes a one-shot ``Sokoboy.cfg`` next to the level, runs the SokoBoy binary, and echoes the
solution file (which contains the ``Approximate LURD:`` line) to stdout.

The SokoBoy binary is built locally and is NOT committed (it's an external GPL-free C++ project);
point this wrapper at it with ``SOKOBOY_BIN``. See ``docs/EXTERNAL-SOLVER.md`` for the full setup.

Usage (normally invoked by solve_corpus, not by hand):
    SOKOBOY_BIN=/path/to/sokoboy SOKO_SOLVER_CMD='python tools/sokoboy_solve.py {level}' \
        python tools/solve_corpus.py --corpus <name>
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# AStar = sub-optimal but tractable on hard/large levels (BFS is optimal but blows up); RSM_Depth=1
# is SokoBoy's recommended default; Rpt_Sol=2 emits the LURD-only solution file.
_SEARCH = os.environ.get("SOKOBOY_SEARCH", "AStar")
_CFG = "PuzzlePath={path}\nSearch={search}\nRSM_Depth={rsm}\nRpt_Sol=2\nRpt_SQInc=0\n"


def solve(xsb_path: str) -> str:
    """Run SokoBoy on ``xsb_path`` and return whatever it wrote (incl. the LURD line), or ""."""
    binary = os.environ.get("SOKOBOY_BIN")
    if not binary or not Path(binary).exists():
        sys.stderr.write("sokoboy_solve: set SOKOBOY_BIN to the locally-built SokoBoy binary "
                         "(see docs/EXTERNAL-SOLVER.md)\n")
        raise SystemExit(2)

    level = Path(xsb_path).resolve()
    workdir = level.parent  # SokoBoy reads Sokoboy.cfg from its CWD and writes output beside the level
    rsm = os.environ.get("SOKOBOY_RSM_DEPTH", "1")
    # SokoBoy globs PuzzlePath via parent_path()+directory_iterator, so the path must be
    # directory-qualified (an absolute path always is).
    (workdir / "Sokoboy.cfg").write_text(_CFG.format(path=str(level), search=_SEARCH, rsm=rsm), encoding="utf-8")

    try:
        timeout = float(os.environ.get("SOKO_SOLVER_TIMEOUT", "300"))
    except ValueError:
        timeout = 300.0
    try:
        subprocess.run([os.path.abspath(binary)], cwd=workdir, capture_output=True,
                       text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""

    # SokoBoy writes <puzzle-stem>_<Search>.txt next to the level; find it (glob is robust to how
    # it derives the stem) and hand its contents back — solve_corpus pulls the LURD run out.
    out = workdir / f"{level.stem}_{_SEARCH}.txt"
    if out.exists():
        return out.read_text(encoding="utf-8", errors="replace")
    matches = sorted(workdir.glob(f"*_{_SEARCH}.txt"))
    return matches[-1].read_text(encoding="utf-8", errors="replace") if matches else ""


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: sokoboy_solve.py <level.xsb>\n")
        raise SystemExit(2)
    sys.stdout.write(solve(sys.argv[1]))


if __name__ == "__main__":
    main()
