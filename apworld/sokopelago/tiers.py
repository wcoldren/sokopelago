"""Difficulty tiers shared by level selection, the ``max_difficulty`` gate, and the
gentle-first-world layout.

A level's ``difficulty`` is the absolute 0..1 score produced offline by
``tools/solve_corpus.py`` (a log-scaled blend of par/search-nodes/moves/boxes). These
cutoffs map that score to an easy/medium/hard tier. The client mirrors ``EASY_MAX`` /
``HARD_MIN`` in ``client/src/main.ts`` (``difficultyTier``) for its badge — keep the two
in sync.
"""

from __future__ import annotations

EASY_MAX = 0.33  # difficulty <  EASY_MAX -> "easy"
HARD_MIN = 0.66  # difficulty >= HARD_MIN -> "hard"

# Tier names ordered easiest-first, so a cap can be expressed as "tier rank <= ceiling".
TIER_ORDER: dict[str, int] = {"easy": 0, "medium": 1, "hard": 2}

# Map the ``max_difficulty`` option key to the highest tier it admits. ``any`` admits
# everything (ceiling = the hardest tier).
MAX_DIFFICULTY_CEILING: dict[str, str] = {"any": "hard", "easy": "easy", "easy_medium": "medium"}


def tier_of(difficulty: float) -> str:
    """Map an absolute 0..1 ``difficulty`` to its tier name."""
    if difficulty >= HARD_MIN:
        return "hard"
    if difficulty >= EASY_MAX:
        return "medium"
    return "easy"


def within_cap(difficulty: float, cap: str) -> bool:
    """Whether a level of this ``difficulty`` is allowed under a tier ``cap`` name
    (``"easy"``/``"medium"``/``"hard"``). ``"hard"`` admits everything."""
    return TIER_ORDER[tier_of(difficulty)] <= TIER_ORDER[cap]
