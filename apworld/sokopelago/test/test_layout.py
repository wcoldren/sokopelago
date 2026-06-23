"""Pure unit tests for the seed-layout helpers (no Archipelago harness needed).

Covers the difficulty-bucketed level selection (``select_bucketed_levels``) and the
``chunk_list`` slicing it feeds. These run without a live multiworld because the helpers
take a plain RNG and a difficulty dict.
"""

import random
import unittest

from ..layout import (
    _allocate,
    chunk_list,
    effective_floor_schedule,
    floor_schedule,
    gentle_first_world,
    select_bucketed_levels,
)

# A monotonic difficulty ramp so "easiest tiers first" is checkable: level n -> n/155.
_DIFF = {n: n / 155 for n in range(1, 156)}


_POOL = list(range(1, 156))  # whole corpus eligible (no max_difficulty cap)


def _select(seed: int, level_count: int = 30, buckets: int = 5) -> list[int]:
    return select_bucketed_levels(_POOL, _DIFF, level_count, buckets, random.Random(seed))


class TestBucketedSelection(unittest.TestCase):
    def test_count_and_uniqueness(self) -> None:
        chosen = _select(1)
        self.assertEqual(len(chosen), 30)
        self.assertEqual(len(set(chosen)), 30)
        self.assertTrue(all(1 <= n <= 155 for n in chosen))

    def test_reproducible_for_same_seed(self) -> None:
        # Same RNG seed -> same draw, so a generated seed is reproducible.
        self.assertEqual(_select(7), _select(7))

    def test_varies_across_seeds(self) -> None:
        # Different seeds draw different puzzles (the whole point of the feature).
        self.assertNotEqual(_select(1), _select(2))

    def test_ramp_is_preserved(self) -> None:
        # The selection is concatenated easiest-tier-first, so the early portion is, on
        # average, easier than the late portion.
        chosen = _select(3)
        third = len(chosen) // 3
        self.assertLess(sum(chosen[:third]) / third, sum(chosen[-third:]) / third)

    def test_full_corpus_selects_everything(self) -> None:
        self.assertEqual(sorted(_select(1, level_count=155)), list(range(1, 156)))

    def test_counts_exact_across_awkward_splits(self) -> None:
        for level_count in (5, 7, 13, 29, 30, 100, 154, 155):
            chosen = _select(9, level_count=level_count, buckets=4)
            self.assertEqual(len(chosen), level_count)
            self.assertEqual(len(set(chosen)), level_count)

    def test_more_buckets_than_levels_is_clamped(self) -> None:
        chosen = _select(4, level_count=5, buckets=12)
        self.assertEqual(len(chosen), 5)
        self.assertEqual(len(set(chosen)), 5)

    def test_missing_difficulty_sorts_as_easiest(self) -> None:
        # Levels without a difficulty score must still be selectable (treated as 0.0).
        chosen = select_bucketed_levels(list(range(1, 21)), {}, 10, 3, random.Random(1))
        self.assertEqual(len(chosen), 10)
        self.assertEqual(len(set(chosen)), 10)

    def test_draws_only_from_the_pool(self) -> None:
        # A max_difficulty cap passes a subset pool; selection must stay within it.
        pool = list(range(1, 42))  # e.g. the easy-tier subset
        chosen = select_bucketed_levels(pool, _DIFF, 20, 5, random.Random(2))
        self.assertEqual(len(chosen), 20)
        self.assertTrue(set(chosen) <= set(pool))


class TestGentleFirstWorld(unittest.TestCase):
    # Levels 1..5 easy (<0.33), 6..15 harder.
    _DIFF = {n: (0.1 if n <= 5 else 0.5) for n in range(1, 16)}

    def _chunk(self, lvls: list[int]) -> list[list[int]]:
        return chunk_list(lvls, 3)

    def test_world_1_is_easy_only(self) -> None:
        worlds = gentle_first_world(list(range(1, 16)), self._DIFF, 0.33, 3, self._chunk)
        self.assertEqual(len(worlds[0]), 3)
        self.assertTrue(all(self._DIFF[n] < 0.33 for n in worlds[0]))
        flat = [n for w in worlds for n in w]
        self.assertEqual(sorted(flat), list(range(1, 16)))  # all present, none lost
        self.assertEqual(len(set(flat)), 15)  # none duplicated

    def test_fewer_easy_than_a_full_world(self) -> None:
        # Only 5 easy levels, region size 3 -> World 1 takes 3 of them; the 2 leftover easy
        # ones fall into later worlds (still all easy in World 1).
        worlds = gentle_first_world(list(range(1, 16)), self._DIFF, 0.33, 3, self._chunk)
        self.assertTrue(all(self._DIFF[n] < 0.33 for n in worlds[0]))

    def test_no_op_without_easy_levels(self) -> None:
        diff = dict.fromkeys(range(1, 7), 0.8)  # all hard -> can't form a gentle world
        worlds = gentle_first_world(list(range(1, 7)), diff, 0.33, 3, self._chunk)
        self.assertEqual(worlds, chunk_list(list(range(1, 7)), 3))

    def test_no_op_when_all_easy(self) -> None:
        diff = dict.fromkeys(range(1, 7), 0.1)  # already entirely easy
        worlds = gentle_first_world(list(range(1, 7)), diff, 0.33, 3, self._chunk)
        self.assertEqual(worlds, chunk_list(list(range(1, 7)), 3))


class TestAllocate(unittest.TestCase):
    def test_sums_to_total_and_never_overfills(self) -> None:
        # Every case has total <= sum(sizes), so the apportionment is exact and in-range.
        for total, sizes in [(10, [3, 3, 3, 3]), (5, [10, 1, 1]), (7, [2, 2, 2, 2]), (0, [4, 4])]:
            alloc = _allocate(total, sizes)
            self.assertEqual(sum(alloc), total)
            self.assertTrue(all(0 <= a <= s for a, s in zip(alloc, sizes, strict=True)))


class TestFloorSchedule(unittest.TestCase):
    """The count-floor chaining schedule (worlds 2..N-1 require their own key plus a floor of
    earlier keys; World 1 free; boss world N reported as all-keys)."""

    def test_degenerate_region_counts(self) -> None:
        self.assertEqual(floor_schedule(0, 2, 0), [])
        self.assertEqual(floor_schedule(1, 2, -1), [0])  # one free world; cap clamped to 0
        self.assertEqual(floor_schedule(2, 2, 0), [0, 1])  # World 1 free, World 2 is the boss

    def test_small_counts(self) -> None:
        self.assertEqual(floor_schedule(3, 2, 1), [0, 0, 2])  # body w2 floor 0; boss = 2
        self.assertEqual(floor_schedule(4, 2, 2), [0, 0, 0, 3])  # body floors (0,0); boss = 3

    def test_group_one_is_a_staircase(self) -> None:
        # group 1: body floor i -> min(i-2, cap); boss -> region_count-1.
        self.assertEqual(floor_schedule(6, 1, 4), [0, 0, 1, 2, 3, 5])

    def test_large_group_flattens_body(self) -> None:
        # group >= world count: every body floor collapses to 0 (the classic single-key star),
        # boss still all-keys.
        self.assertEqual(floor_schedule(6, 100, 4), [0, 0, 0, 0, 0, 5])

    def test_cap_bounds_body_floor(self) -> None:
        floors = floor_schedule(10, 1, 3)  # cap 3
        self.assertTrue(all(f <= 3 for f in floors[1:-1]))  # body floors never exceed the cap
        self.assertEqual(floors[-1], 9)  # boss informational = region_count - 1

    def test_invariant_and_monotonicity(self) -> None:
        # Fillability invariant: a body world's floor never exceeds the count of strictly
        # earlier keyed worlds (i-2), and floors are non-decreasing so spheres nest cleanly.
        for region_count in range(2, 21):
            for group in range(1, 6):
                floors = floor_schedule(region_count, group, region_count - 2)
                self.assertEqual(len(floors), region_count)
                self.assertEqual(floors[0], 0)
                body = floors[1:-1]  # worlds 2..N-1
                for offset, f in enumerate(body):
                    world_index = offset + 2
                    self.assertLessEqual(f, world_index - 2, "floor must not exceed earlier keyed worlds")
                self.assertEqual(body, sorted(body), "body floors must be non-decreasing")


class TestEffectiveFloorSchedule(unittest.TestCase):
    """The fill-robustness guards layered on floor_schedule (flatten zero-slack, bound depth)."""

    def test_non_chained_is_flat(self) -> None:
        self.assertEqual(effective_floor_schedule([5, 5, 5, 5], 1, 4, chained=False), [0, 0, 0, 0])

    def test_single_world(self) -> None:
        self.assertEqual(effective_floor_schedule([5], 2, 4, chained=True), [0])

    def test_zero_slack_flattens_body(self) -> None:
        # 6 size-1 worlds: keys exactly fill the non-boss worlds -> flat body, boss informational.
        self.assertEqual(effective_floor_schedule([1, 1, 1, 1, 1, 1], 1, 4, chained=True), [0, 0, 0, 0, 0, 5])

    def test_default_layout_matches_raw_schedule(self) -> None:
        # 6 worlds, group 2: no guard binds (ceil(6/4)=2, sizes>=3, slack>0) -> raw schedule.
        sizes = [5, 5, 5, 5, 5, 5]
        self.assertEqual(
            effective_floor_schedule(sizes, 2, 4, chained=True),
            floor_schedule(6, 2, 4),
        )

    def test_depth_is_bounded(self) -> None:
        # Steepest group over many worlds: the depth cap keeps the deepest body floor <= max_depth.
        floors = effective_floor_schedule([3] * 20, 1, 4, chained=True)
        self.assertLessEqual(max(floors[1:-1]), 4)

    def test_narrow_worlds_get_at_least_group_two(self) -> None:
        # Size-2 worlds with group 1 must not produce the full i-2 staircase.
        steep = effective_floor_schedule([2] * 8, 1, 99, chained=True)  # max_depth huge -> depth cap off
        self.assertEqual(steep, floor_schedule(8, 2, 6))  # bumped to group 2

    def test_guards_only_raise_floors_never_break_invariant(self) -> None:
        for n in range(2, 18):
            for size in (1, 2, 3, 5):
                for group in (1, 2, 4):
                    floors = effective_floor_schedule([size] * n, group, 4, chained=True)
                    body = floors[1:-1]
                    self.assertEqual(body, sorted(body))  # non-decreasing
                    for offset, f in enumerate(body):
                        # body[offset] is World i = offset+2, so the invariant is floor_i <= i-2 = offset.
                        self.assertLessEqual(f, offset)


class TestChunkList(unittest.TestCase):
    def test_preserves_order_and_sizes(self) -> None:
        self.assertEqual(chunk_list([5, 9, 2, 7, 1], 2), [[5, 9], [2, 7], [1]])

    def test_size_floor_of_one(self) -> None:
        self.assertEqual(chunk_list([1, 2], 0), [[1], [2]])


if __name__ == "__main__":
    unittest.main()
