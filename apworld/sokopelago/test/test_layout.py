"""Pure unit tests for the seed-layout helpers (no Archipelago harness needed).

Covers the difficulty-bucketed level selection (``select_bucketed_levels``) and the
``chunk_list`` slicing it feeds. These run without a live multiworld because the helpers
take a plain RNG and a difficulty dict.
"""

import random
import unittest

from ..layout import _allocate, chunk_list, select_bucketed_levels

# A monotonic difficulty ramp so "easiest tiers first" is checkable: level n -> n/155.
_DIFF = {n: n / 155 for n in range(1, 156)}


def _select(seed: int, level_count: int = 30, buckets: int = 5) -> list[int]:
    return select_bucketed_levels(_DIFF, 155, level_count, buckets, random.Random(seed))


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
        chosen = select_bucketed_levels({}, 20, 10, 3, random.Random(1))
        self.assertEqual(len(chosen), 10)
        self.assertEqual(len(set(chosen)), 10)


class TestAllocate(unittest.TestCase):
    def test_sums_to_total_and_never_overfills(self) -> None:
        # Every case has total <= sum(sizes), so the apportionment is exact and in-range.
        for total, sizes in [(10, [3, 3, 3, 3]), (5, [10, 1, 1]), (7, [2, 2, 2, 2]), (0, [4, 4])]:
            alloc = _allocate(total, sizes)
            self.assertEqual(sum(alloc), total)
            self.assertTrue(all(0 <= a <= s for a, s in zip(alloc, sizes, strict=True)))


class TestChunkList(unittest.TestCase):
    def test_preserves_order_and_sizes(self) -> None:
        self.assertEqual(chunk_list([5, 9, 2, 7, 1], 2), [[5, 9], [2, 7], [1]])

    def test_size_floor_of_one(self) -> None:
        self.assertEqual(chunk_list([1, 2], 0), [[1], [2]])


if __name__ == "__main__":
    unittest.main()
