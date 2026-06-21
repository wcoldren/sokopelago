"""Loads the bundled level manifest (data/microban.json).

The manifest is produced offline by ``tools/solve_corpus.py`` from the canonical
``levels/microban.xsb``. It is the static data table both the apworld and the client
consume — level counts and display names plus the precomputed solvability facts
(push ``par`` and a normalized ``difficulty``). Solving happens only in that offline
tool, never at generation time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class LevelEntry(TypedDict, total=False):
    # ``n``, ``name``, and ``board`` are always present; the solver fields are added by
    # ``tools/solve_corpus.py`` (older manifests may omit them).
    n: int
    name: str
    board: list[str]  # raw XSB rows; the client renders from these
    par: int
    moves: int
    solution: str
    boxes: int
    search_nodes: int  # states the solver expanded (search effort / branching signal)
    difficulty: float
    optimal: bool
    solved: bool
    solver: str  # provenance marker, present only on entries from the external fallback
    requires_pull: bool  # expert corpora: level is unsolvable by pushing alone


_DATA_DIR = Path(__file__).parent / "data"

# Selectable corpora (each has a data/<name>.json manifest). ``microban`` is the standard
# push-only set; ``pullban`` is the expert set with pull-required levels.
CORPUS_NAMES: tuple[str, ...] = ("microban", "pullban")


@dataclass(frozen=True)
class CorpusData:
    """All per-level data the apworld needs from one corpus manifest."""

    name: str
    levels: list[LevelEntry]
    count: int
    name_by_n: dict[int, str]
    par_by_n: dict[int, int]
    difficulty_by_n: dict[int, float]
    solution_by_n: dict[int, str]
    requires_pull: frozenset[int]  # level numbers gated behind the Pull ability


def load_corpus_data(name: str) -> CorpusData:
    """Load and index one corpus manifest by name (e.g. ``"microban"``/``"pullban"``)."""
    levels: list[LevelEntry] = json.loads((_DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return CorpusData(
        name=name,
        levels=levels,
        count=len(levels),
        name_by_n={e["n"]: e["name"] for e in levels},
        par_by_n={e["n"]: e["par"] for e in levels if "par" in e},
        difficulty_by_n={e["n"]: e["difficulty"] for e in levels if "difficulty" in e},
        solution_by_n={e["n"]: e["solution"] for e in levels if "solution" in e},
        requires_pull=frozenset(e["n"] for e in levels if e.get("requires_pull")),
    )


# Largest corpus size — the ceiling for the Level Count / boss-level option ranges
# (generate_early clamps the actual count to the *selected* corpus).
MAX_LEVEL_COUNT: int = max(len(json.loads((_DATA_DIR / f"{n}.json").read_text(encoding="utf-8"))) for n in CORPUS_NAMES)

# Backwards-compatible module-level Microban view (the default corpus).
_MICROBAN = load_corpus_data("microban")
LEVELS: list[LevelEntry] = _MICROBAN.levels
LEVEL_COUNT: int = _MICROBAN.count
NAME_BY_N: dict[int, str] = _MICROBAN.name_by_n
PAR_BY_N: dict[int, int] = _MICROBAN.par_by_n
DIFFICULTY_BY_N: dict[int, float] = _MICROBAN.difficulty_by_n
SOLUTION_BY_N: dict[int, str] = _MICROBAN.solution_by_n
