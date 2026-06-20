"""Escape-valve / trap items must enter the pool without breaking beatability or the
pool-size invariant (one item per location). Each subclass also runs the inherited
WorldTestBase reachability/fill/beatability checks under its option set.
"""

from .bases import SokopelagoTestBase


class TestEscapeValvesFillFromBudget(SokopelagoTestBase):
    # Valve + trap requests that comfortably fit the filler budget: they are carved out
    # of it (so the pool stays exactly level_count) and every valve type appears.
    options = {
        "goal": "beat_final_region",
        "level_count": 30,
        "levels_per_region": 10,
        "skip_tokens": 3,
        "undo_charges": 5,
        "hint_tokens": 3,
        "trap_percentage": 30,
    }

    def test_pool_size_equals_level_count(self) -> None:
        assert len(self.multiworld.itempool) == self.world.level_count

    def test_every_valve_type_present(self) -> None:
        names = {item.name for item in self.multiworld.itempool}
        assert {"Skip Token", "Undo Charge", "Hint Token"} <= names
        assert any(name.startswith("Trap:") for name in names)


class TestTightBudgetKeepsSkip(SokopelagoTestBase):
    # level_count == region count (one level per region) -> budget == 1, so only the
    # highest-priority valve (a Skip Token) fits.
    options = {
        "goal": "beat_final_region",
        "level_count": 10,
        "levels_per_region": 1,
        "skip_tokens": 5,
        "undo_charges": 5,
        "hint_tokens": 5,
        "trap_percentage": 50,
    }

    def test_skip_survives_and_pool_size_holds(self) -> None:
        names = [item.name for item in self.multiworld.itempool]
        assert "Skip Token" in names
        assert len(self.multiworld.itempool) == self.world.level_count


class TestTrapsDisabledByDefault(SokopelagoTestBase):
    # trap_percentage defaults to 0, so no trap items should be created.
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 10}

    def test_no_traps_when_disabled(self) -> None:
        assert not any(item.name.startswith("Trap:") for item in self.multiworld.itempool)
