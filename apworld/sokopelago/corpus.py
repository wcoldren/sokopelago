"""Loads the bundled level manifest (data/microban.json).

The manifest is produced offline by ``tools/solve_corpus.py`` from the canonical
``levels/microban.xsb``. It is the static data table both the apworld and the client
consume — level counts and display names plus the precomputed solvability facts
(push ``par`` and a normalized ``difficulty``). Solving happens only in that offline
tool, never at generation time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class LevelEntry(TypedDict, total=False):
    # ``n`` and ``name`` are always present; the solver fields are added by
    # ``tools/solve_corpus.py`` (older name-only manifests omit them).
    n: int
    name: str
    par: int
    moves: int
    solution: str
    boxes: int
    difficulty: float
    optimal: bool
    solved: bool
    solver: str  # provenance marker, present only on entries from the external fallback


_MANIFEST = Path(__file__).parent / "data" / "microban.json"

LEVELS: list[LevelEntry] = json.loads(_MANIFEST.read_text(encoding="utf-8"))
LEVEL_COUNT: int = len(LEVELS)
NAME_BY_N: dict[int, str] = {entry["n"]: entry["name"] for entry in LEVELS}
PAR_BY_N: dict[int, int] = {entry["n"]: entry["par"] for entry in LEVELS if "par" in entry}
DIFFICULTY_BY_N: dict[int, float] = {entry["n"]: entry["difficulty"] for entry in LEVELS if "difficulty" in entry}
SOLUTION_BY_N: dict[int, str] = {entry["n"]: entry["solution"] for entry in LEVELS if "solution" in entry}
