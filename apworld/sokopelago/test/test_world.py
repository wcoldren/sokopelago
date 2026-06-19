"""Option-range edge cases that exercise the completion_condition branches in
``SokopelagoWorld.set_rules`` (apworld/sokopelago/__init__.py). Each subclass runs the
inherited WorldTestBase reachability/fill/beatability checks under its option set.
"""

from .bases import SokopelagoTestBase


class TestSingleRegion(SokopelagoTestBase):
    # levels_per_region > level_count -> one world -> "always True" completion branch.
    options = {"goal": "beat_final_region", "level_count": 5, "levels_per_region": 50}


class TestMaxLevels(SokopelagoTestBase):
    # Full corpus: 155 levels / 16 worlds.
    options = {"goal": "beat_final_region", "level_count": 155, "levels_per_region": 10}


class TestOneLevelPerRegion(SokopelagoTestBase):
    # Maximum region count for the level count -> many key-gated worlds.
    options = {"goal": "beat_final_region", "level_count": 12, "levels_per_region": 1}


class TestBossLevelDefaultsToLast(SokopelagoTestBase):
    # goal_boss_level = 0 means "the last level in the seed".
    options = {"goal": "boss_level", "level_count": 20, "levels_per_region": 5, "goal_boss_level": 0}


class TestSolveCountAllLevels(SokopelagoTestBase):
    # Target == level_count: needs every keyed world reachable.
    options = {"goal": "solve_count", "level_count": 30, "levels_per_region": 10, "goal_solve_count": 30}
