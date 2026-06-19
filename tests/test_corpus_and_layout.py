import json
from pathlib import Path

import build_corpus
import layout

ROOT = Path(__file__).resolve().parents[1]


class TestBuildCorpus:
    def test_real_manifest_has_155_levels(self):
        data = json.loads((ROOT / "apworld/sokopelago/data/microban.json").read_text())
        assert len(data) == 155
        assert data[0] == {"n": 1, "name": "1"}
        assert data[43] == {"n": 44, "name": "44 — Duh!"}

    def test_parse_levels_counts_and_names(self):
        xsb = "\n".join(
            [
                "; a header comment",
                "",
                "; 1",
                "",
                "#####",
                "#@$.#",
                "#####",
                "",
                "; 2",
                "'Tricky'",
                "",
                "####",
                "#@.#",
                "#$##",
                "####",
            ]
        )
        levels = build_corpus.parse_levels(xsb)
        assert [lvl["n"] for lvl in levels] == [1, 2]
        assert levels[1]["name"] == "2 — Tricky"


class TestChunkLevels:
    def test_even_split(self):
        worlds = layout.chunk_levels(30, 10)
        assert len(worlds) == 3
        assert worlds[0] == list(range(1, 11))
        assert worlds[2] == list(range(21, 31))

    def test_ragged_last_world(self):
        worlds = layout.chunk_levels(25, 10)
        assert [len(w) for w in worlds] == [10, 10, 5]

    def test_size_one_makes_one_world_per_level(self):
        worlds = layout.chunk_levels(5, 1)
        assert len(worlds) == 5
        assert all(len(w) == 1 for w in worlds)


class TestSolveCountKeys:
    def test_zero_when_target_fits_in_free_world(self):
        sizes = [10, 10, 10]
        assert layout.solve_count_keys_needed(sizes, 8) == 0
        assert layout.solve_count_keys_needed(sizes, 10) == 0

    def test_needs_keys_beyond_free_world(self):
        sizes = [10, 10, 10]
        assert layout.solve_count_keys_needed(sizes, 11) == 1
        assert layout.solve_count_keys_needed(sizes, 20) == 1
        assert layout.solve_count_keys_needed(sizes, 21) == 2

    def test_worst_case_uses_smallest_keyed_worlds_first(self):
        # free=10; keyed worlds sized 2 and 8. Reaching 13 needs both worlds in the
        # worst case (10+2 < 13), so the sound bound is 2 keys, not 1.
        sizes = [10, 8, 2]
        assert layout.solve_count_keys_needed(sizes, 13) == 2

    def test_caps_at_available_keys(self):
        sizes = [5, 5]
        assert layout.solve_count_keys_needed(sizes, 10) == 1
        assert layout.solve_count_keys_needed(sizes, 999) == 1  # clamped in practice


class TestBossWorldIndex:
    def test_finds_world_containing_level(self):
        worlds = layout.chunk_levels(30, 10)
        assert layout.boss_world_index(worlds, 1) == 1
        assert layout.boss_world_index(worlds, 15) == 2
        assert layout.boss_world_index(worlds, 30) == 3

    def test_missing_level_falls_back_to_last(self):
        worlds = layout.chunk_levels(10, 10)
        assert layout.boss_world_index(worlds, 999) == 1


class TestClamp:
    def test_clamp(self):
        assert layout.clamp(5, 1, 10) == 5
        assert layout.clamp(-3, 1, 10) == 1
        assert layout.clamp(99, 1, 10) == 10
