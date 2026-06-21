"""The opening puzzle must vary across seeds.

Regression test for the deterministic-opener bug: under default options
(max_difficulty=easy, level_selection=native) every layout path ordered World 1
easiest-first, so the globally-easiest drawn level opened every seed with the same
options. generate_early now shuffles World 1's internal order, so slot_data["levels"][0]
(the opener the client renders first) varies per seed while staying reproducible for a
fixed seed.

SokopelagoTestBase downgrades max_difficulty/gentle_first_world to their pre-0.6 legacy
values for the older tests; this test reproduces the *real* default seed, so it restates
the shipped option defaults (max_difficulty=easy, gentle_first_world on) explicitly — they
override the legacy setdefaults.
"""

from .bases import SokopelagoTestBase


class TestWorld1OpenerVaries(SokopelagoTestBase):
    # Restated apworld defaults (these override the legacy downgrades in SokopelagoTestBase);
    # everything else inherits the shipped Options defaults.
    options = {"max_difficulty": "easy", "gentle_first_world": 1}
    # Build per-seed by hand so we can compare openers across several seeds.
    auto_construct = False

    # Fixed seeds so the test itself is deterministic.
    SEEDS = [1, 2, 3, 4, 5, 17, 42, 99, 123, 1000]

    def _opener_for_seed(self, seed: int) -> int:
        self.world_setup(seed)
        return self.world.fill_slot_data()["levels"][0]

    def test_opener_varies_across_seeds(self) -> None:
        openers = {self._opener_for_seed(seed) for seed in self.SEEDS}
        assert len(openers) > 1, (
            f"opener was identical across {len(self.SEEDS)} seeds ({openers}); World 1 order is not being varied"
        )

    def test_opener_is_reproducible_for_a_fixed_seed(self) -> None:
        first = self._opener_for_seed(12345)
        second = self._opener_for_seed(12345)
        assert first == second, f"same seed produced different openers: {first} != {second}"
