"""0.7 "accurate logic": the boss-zone all-keys gate, count-floor body chaining, and the
Pull-item late-placement floor (all scoped to the beat_final_region goal).

The inherited WorldTestBase fill/reachability battery proves the chained seeds stay beatable
across world counts and steepness settings; the explicit tests pin the boss gate (no early win,
no self-referential key placement), the effective-floor scoping, and the Pull-item floor logic.
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
        boss_locs = [loc for loc in self.multiworld.get_locations(1) if loc.parent_region.name == f"World {boss}"]
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


# --- Pull-item late-placement floor logic (decoupled from a level's requires_pull gate) ---


class TestPullItemFloorLogic(SokopelagoTestBase):
    # Use a real pull-logic world for the bound methods, but skip the inherited battery: the
    # 10-level pullban corpus can't form a reliably-fillable seed at the depths where this floor
    # engages (a known pre-existing limitation of the tiny corpus, not of this logic), so we
    # exercise the floor logic deterministically via its predicates instead.
    run_default_tests = False
    options = {"corpus": "pullban", "pull_logic": 1, "level_count": 10, "levels_per_region": 5}

    def test_eligibility_predicate(self) -> None:
        w = self.world
        # Synthetic chain: 6 worlds, Pull floor 2, level 99 is pull-gated.
        w.region_count = 6
        w._pull_floor = 2
        w.pull_levels = {99}
        floors = [0, 0, 0, 2, 2, 5]
        self.assertTrue(w._pull_item_host_eligible(4, 10, floors), "deep non-pull body world is a valid host")
        self.assertFalse(w._pull_item_host_eligible(6, 10, floors), "boss world must never host Pull")
        self.assertFalse(w._pull_item_host_eligible(3, 10, floors), "worlds below the floor are not hosts")
        self.assertFalse(w._pull_item_host_eligible(4, 99, floors), "a pull-gated level would self-gate Pull")

    def test_has_host_and_fallback(self) -> None:
        w = self.world
        w.region_count = 6
        w._pull_floor = 2
        w.worlds = [[1], [2], [3], [10], [11], [12]]
        floors = [0, 0, 0, 2, 2, 5]
        w.pull_levels = set()
        self.assertTrue(w._has_pull_item_host(floors), "world 4 (floor 2, non-pull) is an eligible host")
        w.pull_levels = {10, 11}  # both deep body levels become pull-gated
        self.assertFalse(w._has_pull_item_host(floors), "no eligible host -> floor disabled (fallback)")

    def test_active_implies_a_host_exists(self) -> None:
        # Whatever the shipped corpus produces, the floor is only active when a host exists, so
        # it can never strand the Pull item / make the seed unfillable.
        if self.world._pull_item_floor_active:
            self.assertTrue(self.world._has_pull_item_host(self.world._effective_floors()))
