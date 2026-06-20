"""Option-range edge cases that exercise the completion_condition branches in
``SokopelagoWorld.set_rules`` (apworld/sokopelago/__init__.py). Each subclass runs the
inherited WorldTestBase reachability/fill/beatability checks under its option set.
"""

from ..layout import chunk_levels
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


class TestDifficultyOrderingOn(SokopelagoTestBase):
    # Difficulty-balanced world assignment must still generate a beatable seed, and the
    # option must actually take effect: the layout differs from the native chunk order
    # while preserving the same world sizes (so key counting / goal logic are unchanged).
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 10, "difficulty_ordering": 1}

    def test_layout_is_reordered_but_same_shape(self) -> None:
        native = chunk_levels(self.world.level_count, self.world.levels_per_region)
        assert self.world.worlds != native, "difficulty_ordering on should rebalance the layout"
        assert [len(w) for w in self.world.worlds] == [len(w) for w in native]
        assert sorted(n for w in self.world.worlds for n in w) == list(range(1, 31))


class TestShuffledBucketsSelection(SokopelagoTestBase):
    # Difficulty-bucketed seed-varied selection: a beatable seed must still result, and
    # the chosen levels must be a valid unique subset of the corpus (not just the first
    # N). The inherited WorldTestBase battery proves fill/reachability with a possibly
    # non-contiguous level set.
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "level_selection": "shuffled_buckets",
        "difficulty_buckets": 5,
    }

    def test_selection_is_a_unique_in_range_subset(self) -> None:
        chosen = [n for w in self.world.worlds for n in w]
        assert len(chosen) == self.world.level_count
        assert len(set(chosen)) == len(chosen), "no level may be selected twice"
        assert all(1 <= n <= self.world.corpus_data.count for n in chosen)

    def test_world_sizes_are_unchanged_by_selection(self) -> None:
        # Same per-world sizes as a native chunking, so key counting / goal logic hold.
        assert sum(len(w) for w in self.world.worlds) == self.world.level_count


class TestShuffledBucketsSolveCount(SokopelagoTestBase):
    # A non-contiguous selection under a non-default goal must still be beatable.
    options = {
        "goal": "solve_count",
        "level_count": 24,
        "levels_per_region": 6,
        "goal_solve_count": 24,
        "level_selection": "shuffled_buckets",
        "difficulty_buckets": 4,
    }


class TestShuffledBucketsBossNearest(SokopelagoTestBase):
    # A boss number that almost certainly isn't drawn (20 of 155 levels) must resolve to
    # the nearest selected level, keeping the boss_level goal valid + beatable.
    options = {
        "goal": "boss_level",
        "level_count": 20,
        "levels_per_region": 5,
        "goal_boss_level": 77,
        "level_selection": "shuffled_buckets",
        "difficulty_buckets": 5,
    }

    def test_boss_resolves_to_nearest_selected_level(self) -> None:
        selected = [n for w in self.world.worlds for n in w]
        assert self.world.boss_level in selected
        expected = min(selected, key=lambda n: (abs(n - 77), n))
        assert self.world.boss_level == expected


class TestDifficultyOrderingOff(SokopelagoTestBase):
    # Native corpus order (the chunk_levels path) must be used verbatim when off.
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 10, "difficulty_ordering": 0}

    def test_layout_is_native_chunk_order(self) -> None:
        native = chunk_levels(self.world.level_count, self.world.levels_per_region)
        assert self.world.worlds == native


class TestPullbanExpert(SokopelagoTestBase):
    # The expert tier on the pull corpus: the Pull item is shuffled in and the
    # pull-required levels are hard-gated behind it. Native order so World 1 holds the
    # push-solvable hosts (a reachable home for Pull / the World 2 Key). The inherited
    # WorldTestBase fill/reachability battery proves the gated seed is still beatable.
    options = {
        "corpus": "pullban",
        "pull_logic": 1,
        "level_count": 10,
        "levels_per_region": 5,
        "difficulty_ordering": 0,
    }

    def test_pull_item_is_progression_and_gates_exist(self) -> None:
        pull = [i for i in self.multiworld.itempool if i.name == "Pull"]
        assert len(pull) == 1 and pull[0].advancement
        assert self.world.pull_levels, "expert pullban should have pull-gated levels"

    def test_gated_levels_are_a_subset_of_the_corpus_pull_levels(self) -> None:
        assert self.world.pull_levels <= set(self.world.corpus_data.requires_pull)


class TestPullbanNoExpert(SokopelagoTestBase):
    # Same corpus without expert logic: no Pull item, nothing gated, still beatable.
    options = {
        "corpus": "pullban",
        "pull_logic": 0,
        "level_count": 10,
        "levels_per_region": 5,
        "difficulty_ordering": 0,
    }

    def test_no_pull_item_and_no_gates(self) -> None:
        assert "Pull" not in {i.name for i in self.multiworld.itempool}
        assert not self.world.pull_levels
