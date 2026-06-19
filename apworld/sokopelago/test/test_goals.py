"""Each goal mode generates a beatable single-player world.

WorldTestBase auto-runs, per subclass with ``options``:
  - test_all_state_can_reach_everything  (all items collected -> everything reachable)
  - test_empty_state_can_reach_something (no items -> at least one location reachable)
  - test_fill                            (fill completes and the seed is beatable)
"""

from .bases import SokopelagoTestBase


class TestBeatFinalRegion(SokopelagoTestBase):
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
    }


class TestSolveCount(SokopelagoTestBase):
    options = {
        "goal": "solve_count",
        "level_count": 40,
        "levels_per_region": 10,
        "goal_solve_count": 25,
    }


class TestBossLevel(SokopelagoTestBase):
    options = {
        "goal": "boss_level",
        "level_count": 30,
        "levels_per_region": 10,
        "goal_boss_level": 17,
    }
