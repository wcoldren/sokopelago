"""0.7 "accurate logic": the boss-zone all-keys gate and count-floor body chaining (both scoped
to the beat_final_region goal).

The inherited WorldTestBase fill/reachability battery proves the chained seeds stay beatable
across world counts and steepness settings; the explicit tests pin the boss gate (no early win,
no self-referential key placement) and the effective-floor scoping.
"""

from BaseClasses import CollectionState
from Fill import distribute_items_restrictive

from ..Items import world_key_name
from .bases import SokopelagoTestBase

# --- Chaining stays fillable/beatable across world counts (inherits the fill battery) ---


class TestChainSteepCapped(SokopelagoTestBase):
    # Steepest user setting (group 1) over many narrow worlds: the effective-depth cap keeps it
    # a reliable fill while the inherited battery confirms it is still beatable.
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 2, "chain_group": 1}


class TestChainDefault(SokopelagoTestBase):
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 5, "chain_group": 2}


class TestChainManyWorlds(SokopelagoTestBase):
    options = {"goal": "beat_final_region", "level_count": 60, "levels_per_region": 3, "chain_group": 2}


class TestChainTinyPool(SokopelagoTestBase):
    options = {"goal": "beat_final_region", "level_count": 6, "levels_per_region": 2, "chain_group": 1}


class TestChainFlatBackCompat(SokopelagoTestBase):
    # chain_group >= world count flattens the body floors back to the classic single-key star
    # (the boss all-keys gate still applies).
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 5, "chain_group": 50}

    def test_body_floors_are_flat(self) -> None:
        floors = self.world._effective_floors()
        self.assertTrue(all(f == 0 for f in floors[:-1]), "a large chain_group must flatten every body floor")


# --- Boss-zone gate: deepest sphere, no early win, no self-referential key placement ---


class TestBossGate(SokopelagoTestBase):
    options = {"goal": "beat_final_region", "level_count": 30, "levels_per_region": 5, "chain_group": 2}

    def test_no_key_in_boss_world(self) -> None:
        # The boss world gates on ALL keys, so a key placed there would need itself to be
        # reachable — fill must keep every key out of the boss region.
        distribute_items_restrictive(self.multiworld)
        boss = self.world.region_count
        key_names = {world_key_name(n) for n in range(2, boss + 1)}
        boss_locs = [
            loc
            for loc in self.multiworld.get_locations(1)
            if loc.parent_region is not None and loc.parent_region.name == f"World {boss}"
        ]
        self.assertTrue(boss_locs, "boss world should have locations")
        for loc in boss_locs:
            self.assertFalse(
                loc.item is not None and loc.item.name in key_names,
                f"a world key was placed in the boss world: {loc}",
            )

    def test_not_completable_before_all_keys(self) -> None:
        player = self.player
        all_keys = [world_key_name(n) for n in range(2, self.world.region_count + 1)]
        self.assertGreater(len(all_keys), 1, "need a multi-world seed to exercise the gate")
        cc = self.multiworld.completion_condition[player]
        state = CollectionState(self.multiworld)
        for name in all_keys[:-1]:  # every key but the last
            state.collect(self.world.create_item(name), True)
        self.assertFalse(cc(state), "seed must not be completable before all keys are held (no early win)")
        state.collect(self.world.create_item(all_keys[-1]), True)
        self.assertTrue(cc(state), "holding all keys must satisfy completion")


# --- Effective-floor scoping (beat_final_region only; zero-slack flatten) ---


class TestEffectiveFloorsSolveCount(SokopelagoTestBase):
    # Non-beat_final_region goals keep the flat 0.6 single-key layout.
    options = {"goal": "solve_count", "level_count": 30, "levels_per_region": 5, "goal_solve_count": 15}

    def test_flat_floors_for_non_beat_final(self) -> None:
        self.assertEqual(self.world._effective_floors(), [0] * self.world.region_count)


class TestEffectiveFloorsZeroSlack(SokopelagoTestBase):
    # levels_per_region == 1 -> keys exactly fill the non-boss worlds (zero slack), so the body
    # floors flatten and only the all-keys boss gate remains (keeps the tight fill reliable).
    options = {"goal": "beat_final_region", "level_count": 12, "levels_per_region": 1, "chain_group": 1}

    def test_zero_slack_flattens_body(self) -> None:
        floors = self.world._effective_floors()
        self.assertTrue(all(f == 0 for f in floors[:-1]), "zero-slack layout must flatten body floors")
        self.assertEqual(floors[-1], self.world.region_count - 1, "boss entry stays informational all-keys")
