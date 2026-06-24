"""Player options for Sokopelago."""

from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range, Toggle

from .corpus import MAX_LEVEL_COUNT


class Corpus(Choice):
    """Which level corpus to play.
    microban: the standard 155-level Microban set (push-only).
    pullban: a small expert set whose harder levels require the Pull ability (see
    Pull Logic).
    autoban: an in-house generated push-only set with a calibrated easy/medium/hard
    spread (original by construction).
    curated: a large merged pool of solved levels across all curated sets (Microban I-III,
    Sasquatch, etc.), re-indexed — for variety; built by tools/build_pool.py."""

    display_name = "Corpus"
    option_microban = 0
    option_pullban = 1
    option_autoban = 2
    option_curated = 3
    default = 0


class LevelCount(Range):
    """How many levels are included in the seed. The first N levels of the corpus are
    used (preserving the corpus's difficulty ramp)."""

    display_name = "Level Count"
    range_start = 5
    range_end = MAX_LEVEL_COUNT
    default = 30


class LevelSelection(Choice):
    """How the seed's levels are drawn from the corpus.
    shuffled_buckets (default): vary the selection per seed. Levels are grouped into
    Difficulty Buckets tiers and a size-proportional, randomly-shuffled subset of each tier
    is drawn, so different seeds play different puzzles while the easy→hard ramp is kept.
    With this, Goal Boss Level may name a level that isn't drawn — the nearest selected level
    is used instead.
    native: the first Level Count levels in corpus order (deterministic — every seed with
    the same options gets the same puzzles); choose this when you want reproducible seeds."""

    display_name = "Level Selection"
    option_native = 0
    option_shuffled_buckets = 1
    default = 1


class DifficultyBuckets(Range):
    """Number of difficulty tiers used by the shuffled_buckets Level Selection (ignored
    by native selection). More buckets = a tighter difficulty ramp with less variety
    within a tier; fewer = more variety but coarser ramping."""

    display_name = "Difficulty Buckets"
    range_start = 2
    range_end = 12
    default = 5


class MaxDifficulty(Choice):
    """Cap the seed's level pool to a difficulty tier ceiling (using each level's
    precomputed difficulty score).
    any: no cap — the whole corpus is eligible.
    easy: only easy-tier puzzles — a gentle, low-frustration seed.
    easy_medium: easy and medium tiers, excluding the hardest puzzles.
    Defaults to easy (so the generated template and any bare YAML stay gentle); raise it
    once you want tougher puzzles. The cap filters the corpus *before* selection, so Level
    Count draws from the capped pool (and is clamped down to it when the cap leaves fewer
    levels than requested)."""

    display_name = "Max Difficulty"
    option_any = 0
    option_easy = 1
    option_easy_medium = 2
    default = 1


class LevelsPerRegion(Range):
    """How many levels per region ("world"). Each world after the first is opened by a
    "World n Key" item shuffled into the multiworld."""

    display_name = "Levels Per Region"
    range_start = 1
    range_end = 50
    default = 5


class ChainGroup(Range):
    """How steeply later worlds chain behind earlier-world keys (count-floor chaining,
    beat_final_region goal only). Body world i (2..N-1) requires its own key AND at least
    floor((i-2) / Chain Group) *other* keys already held, so progress fans out instead of
    every world opening the instant its lone key is found. Lower = steeper (you must clear
    more of the earlier worlds first); a value >= the world count flattens it back to the
    classic "any key opens its world" star. The final (boss) world always needs every key
    regardless of this setting. Default 2 (a gentle step every couple of worlds)."""

    display_name = "Chain Group"
    range_start = 1
    range_end = MAX_LEVEL_COUNT  # large value => flat / back-compat
    default = 2


class Goal(Choice):
    """The win condition.
    beat_final_region: reach the last world (hold its key).
    solve_count: solve a target number of levels (Goal Solve Count).
    boss_level: reach the world containing a designated boss level (Goal Boss Level).
    beat_final_region (the default) is the supported, tested goal: the final world gates on all
    keys and body worlds chain behind earlier keys (see docs/DESIGN-boss-zone.md). solve_count and
    boss_level are experimental — they keep the simpler single-key layout (no chaining/boss gate)."""

    display_name = "Goal"
    option_beat_final_region = 0
    option_solve_count = 1
    option_boss_level = 2
    default = 0


class GoalSolveCount(Range):
    """For the solve_count goal: how many levels must be solved. Clamped to Level Count."""

    display_name = "Goal Solve Count"
    range_start = 1
    range_end = MAX_LEVEL_COUNT
    default = 15


class GoalBossLevel(Range):
    """For the boss_level goal: which Microban number is the boss. 0 means "the last
    (highest-numbered) level in the seed". If the chosen number isn't one of the seed's
    levels (possible with shuffled_buckets selection), the nearest selected level is used."""

    display_name = "Goal Boss Level"
    range_start = 0
    range_end = MAX_LEVEL_COUNT
    default = 0


class SkipTokens(Range):
    """How many Skip Tokens to shuffle into the pool. Consume one to mark a level you
    can't solve as cleared (it sends its check) so a skill wall can't permanently
    stall your slot. Escape-valve items are carved out of the filler budget, so very
    high counts are clamped to the room available."""

    display_name = "Skip Tokens"
    range_start = 0
    range_end = 50
    default = 3


class UndoCharges(Range):
    """How many Undo Charges to shuffle into the pool. Each grants one move-undo in the
    client."""

    display_name = "Undo Charges"
    range_start = 0
    range_end = 50
    default = 5


class HintTokens(Range):
    """How many Hint Tokens to shuffle into the pool. Consume one to reveal the next
    move of a level's solution."""

    display_name = "Hint Tokens"
    range_start = 0
    range_end = 50
    default = 3


class TrapPercentage(Range):
    """Percent of the filler budget to replace with (presentation-only) trap items.
    0 disables traps."""

    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0


class DifficultyOrdering(Toggle):
    """Balance measured difficulty across worlds (and order each world easiest-first)
    so the non-linear key order can't drop you onto a brutal world first. When off,
    worlds follow the corpus's native order."""

    display_name = "Difficulty Ordering"
    default = 1


class GentleFirstWorld(Toggle):
    """Keep World 1 ("sphere 1") to easy-tier puzzles only, for a gentle start, even when
    the rest of the seed spans harder tiers. The hardest of an otherwise-easy first world
    are pushed back into later worlds. No-op when the seed has no easy levels, or when it
    is already entirely easy (e.g. Max Difficulty = easy). On by default."""

    display_name = "Gentle First World"
    default = 1


class ParChecks(Toggle):
    """Add a second location per level: "Solve Microban n in <= par pushes". Solving a
    level within its precomputed push-par sends this extra check, roughly doubling the
    seed's check count. These locations only ever hold filler (never progression), so a
    hard par requirement can't soft-lock the seed. Off by default."""

    display_name = "Par Checks"
    default = 0


class EfficiencyChecks(Toggle):
    """Add an "efficient" tier on top of Par Checks: a third location per level, "Solve
    Microban n efficiently". It's a *gettable* efficiency reward — it sends when you
    solve within Efficiency Margin percent of the optimal push count (whereas the Par
    Checks location demands exactly optimal). Like par locations these only hold filler
    (EXCLUDED), so they can't soft-lock the seed. Off by default; has no effect unless
    Par Checks is also on."""

    display_name = "Efficiency Checks"
    default = 0


class EfficiencyMargin(Range):
    """For Efficiency Checks: how many percent over the optimal push count still counts
    as an "efficient" solve. The efficient tier sends when pushes <= floor(optimal *
    (1 + this/100)). 0 makes it identical to the perfect (Par Checks) tier."""

    display_name = "Efficiency Margin"
    range_start = 0
    range_end = 100
    default = 15


class PullLogic(Toggle):
    """Pull ability-logic tier. When on, levels that require the Pull ability are
    hard-gated behind a "Pull" progression item shuffled into the multiworld — you can't
    solve (or send checks for) those levels until you receive Pull. When off, the Pull
    mechanic is simply always available and nothing is gated. Only has an effect with a
    corpus that has pull-required levels (e.g. pullban); a no-op on Microban. Off by
    default. (Renamed from the old `expert_logic` in 0.6.0.)"""

    display_name = "Pull Logic"
    default = 0


@dataclass
class SokopelagoOptions(PerGameCommonOptions):
    corpus: Corpus
    level_count: LevelCount
    level_selection: LevelSelection
    difficulty_buckets: DifficultyBuckets
    max_difficulty: MaxDifficulty
    levels_per_region: LevelsPerRegion
    chain_group: ChainGroup
    goal: Goal
    goal_solve_count: GoalSolveCount
    goal_boss_level: GoalBossLevel
    skip_tokens: SkipTokens
    undo_charges: UndoCharges
    hint_tokens: HintTokens
    trap_percentage: TrapPercentage
    difficulty_ordering: DifficultyOrdering
    gentle_first_world: GentleFirstWorld
    par_checks: ParChecks
    efficiency_checks: EfficiencyChecks
    efficiency_margin: EfficiencyMargin
    pull_logic: PullLogic
