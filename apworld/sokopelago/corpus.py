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
    # Offline annotation fields (added by ``tools/annotate_corpus.py``; dev/dataset use only —
    # the apworld and client ignore them, so they are purely additive). Curated third-party
    # corpora carry these; the shipped microban/pullban/autoban manifests need not.
    box_change_difficulty: float
    fun_features: dict  # {playable_area, openness, boxes, steps_per_box, search_difficulty, likeability}
    # structural: goal_room_connected, matter_fraction, matter_method, dead_floor_ratio, box_density, deadlock_proximity
    structural: dict
    quality_score: float
    canonical_hash: str  # symmetry+player-region invariant identity (tools/canonical.py)
    provenance: str  # corpus key into levels/provenance.json
    license: str  # license_id from the provenance entry


_DATA_DIR = Path(__file__).parent / "data"

# Selectable corpora (each has a data/<name>.json manifest). ``microban`` is the standard
# push-only set; ``pullban`` is the expert set with pull-required levels; ``autoban`` is the
# in-house generated push-only set (``tools/generate_corpus.py``), difficulty-calibrated to
# Microban's scale.
CORPUS_NAMES: tuple[str, ...] = ("microban", "pullban", "autoban", "curated")


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


# Registered location-id ceiling: ``Locations.py`` registers "Solve … n" ids for n in
# 1..LOCATION_MAX (each band is 10_000 wide, so this can grow to ~9_999 before bands collide).
# A corpus may not exceed it — every selected level n needs a pre-registered location id. This
# only ever *grows* the location map (ids 1..155 are unchanged), so it's backward-compatible.
LOCATION_MAX: int = 999

# Largest corpus size — the ceiling for the Level Count / boss-level option ranges
# (generate_early clamps the actual count to the *selected* corpus).
MAX_LEVEL_COUNT: int = max(len(json.loads((_DATA_DIR / f"{n}.json").read_text(encoding="utf-8"))) for n in CORPUS_NAMES)
assert MAX_LEVEL_COUNT <= LOCATION_MAX, (
    f"corpus has {MAX_LEVEL_COUNT} levels but only {LOCATION_MAX} location ids are registered "
    f"(raise LOCATION_MAX in corpus.py — keep it < 10_000 so the id bands don't collide)."
)

# Backwards-compatible module-level Microban view (the default corpus).
_MICROBAN = load_corpus_data("microban")
LEVELS: list[LevelEntry] = _MICROBAN.levels
LEVEL_COUNT: int = _MICROBAN.count
NAME_BY_N: dict[int, str] = _MICROBAN.name_by_n
PAR_BY_N: dict[int, int] = _MICROBAN.par_by_n
DIFFICULTY_BY_N: dict[int, float] = _MICROBAN.difficulty_by_n
SOLUTION_BY_N: dict[int, str] = _MICROBAN.solution_by_n
