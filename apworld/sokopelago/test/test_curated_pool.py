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
