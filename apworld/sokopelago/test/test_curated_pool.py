"""The merged ``curated`` corpus (re-indexed > 155 levels) must generate a valid seed — proving the
lifted location-id cap works end-to-end through the apworld, not just in the id registry.
"""

from .bases import SokopelagoTestBase


class TestCuratedTenByTen(SokopelagoTestBase):
    # 10 worlds x 10 puzzles, drawn from the >155-level curated pool across the full difficulty range.
    options = {
        "corpus": "curated",
        "goal": "beat_final_region",
        "level_count": 100,
        "levels_per_region": 10,
        "max_difficulty": "any",
        "level_selection": "shuffled_buckets",
    }

    def test_ten_worlds_of_ten(self) -> None:
        self.assertGreater(self.world.corpus_data.count, 155)  # the pool exceeds the old cap
        self.assertEqual(self.world.level_count, 100)
        self.assertEqual(self.world.region_count, 10)
        self.assertTrue(all(len(w) == 10 for w in self.world.worlds))

    def test_locations_exist_for_high_level_numbers(self) -> None:
        # Every selected level (n can exceed 155) has a registered "Solve …" location.
        names = {loc.name for region in self.multiworld.regions for loc in region.locations}
        for world in self.world.worlds:
            for n in world:
                self.assertIn(f"Solve Microban {n}", names)

    def test_curated_has_no_pull_required_levels(self) -> None:
        # The soundness fix: curated ships with pull_logic off, so it must contain NO pull-required
        # level — otherwise AP's fill treats an unsolvable-by-push level as push-solvable and the
        # seed can stall. (build_pool.py filters them out; this guards the bundled data.)
        self.assertEqual(self.world.corpus_data.requires_pull, frozenset())

    def test_curated_pull_logic_off_grants_no_pull_item(self) -> None:
        # With no pull-required levels there is nothing to gate, so no Pull item is shuffled in and
        # nothing is gated. The inherited WorldTestBase fill/reachability battery proves the seed
        # is still beatable on a pure-push run.
        self.assertFalse(self.world.pull_levels)
        self.assertNotIn("Pull", {item.name for item in self.multiworld.itempool})
