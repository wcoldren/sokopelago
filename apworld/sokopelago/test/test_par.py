"""Phase 4 — par-check locations ("Solve Microban n in <= par pushes").

When the Par Checks option is on, each level gets a second location in a parallel id
band. They are EXCLUDED (filler-only) so a hard par requirement can't strand a
progression item. Each subclass also runs the inherited WorldTestBase
reachability/fill/beatability checks under its option set.
"""

from BaseClasses import LocationProgressType

from .bases import SokopelagoTestBase

_PAR_SUFFIX = "in <= par pushes"
_EFF_SUFFIX = "efficiently"


def _par_locations(world_test):
    return [loc for loc in world_test.multiworld.get_locations(world_test.player) if loc.name.endswith(_PAR_SUFFIX)]


def _eff_locations(world_test):
    return [loc for loc in world_test.multiworld.get_locations(world_test.player) if loc.name.endswith(_EFF_SUFFIX)]


class TestParChecksEnabled(SokopelagoTestBase):
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "par_checks": 1,
    }

    def test_par_location_per_level(self) -> None:
        # Exactly one par location per seed level, on top of the solve locations.
        par_locs = _par_locations(self)
        assert len(par_locs) == self.world.level_count
        all_locs = [loc for loc in self.multiworld.get_locations(self.player) if loc.name.startswith("Solve Microban")]
        assert len(all_locs) == 2 * self.world.level_count

    def test_par_locations_are_excluded(self) -> None:
        # EXCLUDED is the mechanism that keeps progression off these skill-walled checks.
        assert all(loc.progress_type == LocationProgressType.EXCLUDED for loc in _par_locations(self))

    def test_pool_size_matches_location_count(self) -> None:
        assert len(self.multiworld.itempool) == 2 * self.world.level_count


class TestEfficiencyChecksEnabled(SokopelagoTestBase):
    # Par + Efficiency on: three locations per level (solve / perfect / efficient). The
    # efficient tier is also EXCLUDED (filler-only) and the pool grows to match.
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "par_checks": 1,
        "efficiency_checks": 1,
        "efficiency_margin": 15,
    }

    def test_three_locations_per_level(self) -> None:
        assert len(_eff_locations(self)) == self.world.level_count
        assert len(_par_locations(self)) == self.world.level_count
        all_locs = [loc for loc in self.multiworld.get_locations(self.player) if loc.name.startswith("Solve Microban")]
        assert len(all_locs) == 3 * self.world.level_count

    def test_efficiency_locations_are_excluded(self) -> None:
        assert all(loc.progress_type == LocationProgressType.EXCLUDED for loc in _eff_locations(self))

    def test_pool_size_matches_location_count(self) -> None:
        assert len(self.multiworld.itempool) == 3 * self.world.level_count

    def test_slot_data_ships_efficiency_fields(self) -> None:
        data = self.world.fill_slot_data()
        assert data["efficiency_checks"] is True
        assert data["efficiency_margin"] == 15


class TestEfficiencyChecksRequireParChecks(SokopelagoTestBase):
    # Efficiency on but Par off: the efficiency tier is a no-op (no extra locations), and
    # slot_data reports it disabled so the client won't expect the check.
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "par_checks": 0,
        "efficiency_checks": 1,
    }

    def test_no_efficiency_locations_without_par(self) -> None:
        assert _eff_locations(self) == []
        assert _par_locations(self) == []
        assert len(self.multiworld.itempool) == self.world.level_count

    def test_slot_data_reports_efficiency_disabled(self) -> None:
        assert self.world.fill_slot_data()["efficiency_checks"] is False


class TestParChecksOff(SokopelagoTestBase):
    # Default off: no par locations, pool size unchanged (one item per level).
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 10, "par_checks": 0}

    def test_no_par_locations(self) -> None:
        assert _par_locations(self) == []

    def test_pool_size_equals_level_count(self) -> None:
        assert len(self.multiworld.itempool) == self.world.level_count


class TestParChecksMaxLevels(SokopelagoTestBase):
    # Worst-case load: 155 levels x 2 = 310 locations must still fill + stay beatable.
    options = {"goal": "beat_final_region", "level_count": 155, "levels_per_region": 10, "par_checks": 1}

    def test_full_corpus_par_locations(self) -> None:
        assert len(_par_locations(self)) == 155
        assert len(self.multiworld.itempool) == 310


class TestParChecksWithTraps(SokopelagoTestBase):
    # Par on + traps: trap density tracks level_count (not the doubled budget), and the
    # pool still equals the location count.
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "par_checks": 1,
        "trap_percentage": 20,
        "skip_tokens": 3,
        "undo_charges": 5,
        "hint_tokens": 3,
    }

    def test_pool_size_and_trap_density(self) -> None:
        items = list(self.multiworld.itempool)
        assert len(items) == 2 * self.world.level_count
        traps = [it for it in items if it.name.startswith("Trap:")]
        # 20% of level_count (30) = 6 traps — not 20% of the doubled budget.
        assert len(traps) == (30 * 20) // 100
