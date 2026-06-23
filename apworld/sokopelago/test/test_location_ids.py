"""The location/world id registry is lifted past Microban's 155 so a large merged corpus is
selectable. This must stay BACKWARD-COMPATIBLE: ids for level numbers 1..155 are unchanged (so
existing seeds/multiworlds keep working), and the registry only *grows*.
"""

import unittest

from .. import Items, Locations, corpus


class TestLocationIdRegistry(unittest.TestCase):
    def test_ids_1_to_155_unchanged(self) -> None:
        # The original 155 Microban levels must keep their exact ids in every band.
        for n in range(1, 156):
            self.assertEqual(Locations.location_name_to_id[Locations.solve_location_name(n)], Locations.LOC_ID_BASE + n)
            self.assertEqual(
                Locations.location_name_to_id[Locations.par_location_name(n)], Locations.PAR_LOC_ID_BASE + n
            )
            self.assertEqual(
                Locations.location_name_to_id[Locations.eff_location_name(n)], Locations.EFF_LOC_ID_BASE + n
            )

    def test_registry_covers_the_lifted_range(self) -> None:
        self.assertGreater(corpus.LOCATION_MAX, 155)
        self.assertEqual(len(Locations.location_name_to_id), corpus.LOCATION_MAX * 3)
        # A level number well past 155 (e.g. a 300-level merged pool) has a registered location.
        self.assertIn(Locations.solve_location_name(300), Locations.location_name_to_id)

    def test_no_id_band_collisions(self) -> None:
        # Solve band stays clear of the par band (10_000 apart -> safe to ~9_999 levels).
        self.assertLess(Locations.LOC_ID_BASE + corpus.LOCATION_MAX, Locations.PAR_LOC_ID_BASE)
        # World-key band stays clear of the escape-valve band (keys = KEY_ID_BASE + n).
        self.assertLess(Items.KEY_ID_BASE + Items.MAX_WORLDS, Items.SKIP_ID)

    def test_corpus_size_fits_registered_ids(self) -> None:
        self.assertLessEqual(corpus.MAX_LEVEL_COUNT, corpus.LOCATION_MAX)
