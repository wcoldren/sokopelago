"""Player options for Sokopelago (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range

from .corpus import LEVEL_COUNT


class Corpus(Choice):
    """Which level corpus to play. Only Microban (155 levels) is available for now."""

    display_name = "Corpus"
    option_microban = 0
    default = 0


class LevelCount(Range):
    """How many levels are included in the seed. The first N levels of the corpus are
    used (preserving the corpus's difficulty ramp)."""

    display_name = "Level Count"
    range_start = 5
    range_end = LEVEL_COUNT
    default = 30


class LevelsPerRegion(Range):
    """How many levels per region ("world"). Each world after the first is opened by a
    "World n Key" item shuffled into the multiworld."""

    display_name = "Levels Per Region"
    range_start = 1
    range_end = 50
    default = 10


class Goal(Choice):
    """The win condition.
    beat_final_region: reach the last world (hold its key).
    solve_count: solve a target number of levels (Goal Solve Count).
    boss_level: reach the world containing a designated boss level (Goal Boss Level)."""

    display_name = "Goal"
    option_beat_final_region = 0
    option_solve_count = 1
    option_boss_level = 2
    default = 0


class GoalSolveCount(Range):
    """For the solve_count goal: how many levels must be solved. Clamped to Level Count."""

    display_name = "Goal Solve Count"
    range_start = 1
    range_end = LEVEL_COUNT
    default = 15


class GoalBossLevel(Range):
    """For the boss_level goal: which Microban number is the boss. 0 means "the last
    level in the seed". Clamped into the selected level range."""

    display_name = "Goal Boss Level"
    range_start = 0
    range_end = LEVEL_COUNT
    default = 0


@dataclass
class SokopelagoOptions(PerGameCommonOptions):
    corpus: Corpus
    level_count: LevelCount
    levels_per_region: LevelsPerRegion
    goal: Goal
    goal_solve_count: GoalSolveCount
    goal_boss_level: GoalBossLevel
