import json
from pathlib import Path

import build_corpus
import layout
import solve_corpus
import xsb_levels

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apworld/sokopelago/data/microban.json"


class TestBuildCorpus:
    def test_real_manifest_has_155_levels(self):
        data = json.loads(MANIFEST.read_text())
        assert len(data) == 155
        assert data[0]["n"] == 1 and data[0]["name"] == "1"
        assert data[43]["n"] == 44 and data[43]["name"] == "44 — Duh!"

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


class TestEnrichedManifest:
    """The committed manifest must carry valid, replayable solver data for every level.

    Coverage is 155/155: the pure-Python search solves all but a couple of stubborn
    levels, and those are filled by the build-time external-solver fallback
    (``SOKO_SOLVER_CMD``), flagged ``"solver": "external"``. Regenerating without that
    solver configured leaves the hardest level(s) ``solved=False``; the allowance below
    only exists to keep such a partial local rebuild from hard-failing this test."""

    MAX_UNSOLVED = 1  # only the external-solver-dependent level(s) may regress locally

    def test_every_entry_has_base_fields(self):
        data = json.loads(MANIFEST.read_text())
        assert len(data) == 155
        for e in data:
            for key in ("n", "name", "boxes", "difficulty", "optimal", "solved"):
                assert key in e, f"level {e.get('n')} missing {key}"
            assert 0.0 <= e["difficulty"] <= 1.0

    def test_committed_manifest_solves_every_level(self):
        # The committed artifact is the deliverable: a verified solution for all 155.
        data = json.loads(MANIFEST.read_text())
        unsolved = [e["n"] for e in data if not e.get("solved")]
        assert unsolved == [], f"committed manifest is missing solutions for: {unsolved}"

    def test_solved_levels_have_replayable_solutions(self):
        data = {e["n"]: e for e in json.loads(MANIFEST.read_text())}
        levels = {lvl.n: lvl for lvl in xsb_levels.load_corpus()}
        for n, lvl in levels.items():
            e = data[n]
            if not e.get("solved"):
                continue
            assert e["par"] >= 1
            assert e["moves"] >= e["par"]  # each push is one move; walks only add more
            assert solve_corpus.replay(lvl, e["solution"]), f"level {n} solution does not solve it"

    def test_few_levels_are_unsolved(self):
        data = json.loads(MANIFEST.read_text())
        unsolved = [e["n"] for e in data if not e.get("solved")]
        assert len(unsolved) <= self.MAX_UNSOLVED, f"too many unsolved levels: {unsolved}"


class TestSolverTechniques:
    """Unit coverage for the prunings/macros layered on the index-space search:
    freeze-deadlock detection, tunnel macros, and PI-corral pruning."""

    def _solver(self, board: str):
        lvl = xsb_levels.parse_levels(f"; t\n\n{board}")[0]
        return lvl, solve_corpus.Solver(lvl)

    def test_freeze_deadlock_corner_off_goal(self):
        # A box shoved into a non-goal corner can never move again -> deadlock.
        _, s = self._solver("######\n#@   #\n#  ..#\n#  ..#\n######")
        corner = s.idx[(1, 1)]
        assert s.freeze_deadlock(corner, frozenset({corner})) is True

    def test_freeze_ok_on_goal(self):
        # A box frozen in a corner that *is* a goal is fine, not a deadlock.
        _, s = self._solver("######\n#@   #\n#  ..#\n#  ..#\n######")
        on_goal = s.idx[(4, 3)]  # a corner cell that is a goal
        assert s.freeze_deadlock(on_goal, frozenset({on_goal})) is False

    def test_freeze_ok_when_movable(self):
        # A box in the open interior of a roomy level is not frozen.
        _, s = self._solver("########\n#@     #\n#      #\n#  ..  #\n#  ..  #\n#      #\n########")
        movable = s.idx[(3, 2)]  # open floor next to the goals, pushable in several dirs
        assert s.freeze_deadlock(movable, frozenset({movable})) is False

    def test_tunnel_macro_collapses_forced_pushes(self):
        # One box pushed straight down a one-wide corridor: a single macro edge, par=3,
        # and the move string is exactly the three pushes (no stray walks).
        lvl, _ = self._solver("#######\n#@$  .#\n#######")
        e = solve_corpus.solve(lvl)
        assert e["solution"] == "RRR"
        assert e["par"] == 3
        assert solve_corpus.replay(lvl, e["solution"]) is True

    def test_pi_corral_fires_when_boxes_only_push_inward(self):
        # Real corpus level 111: the player starts boxed into a tiny pocket whose
        # surrounding boxes can currently only be pushed into the enclosed area.
        lvl = {x.n: x for x in xsb_levels.load_corpus()}[111]
        s = solve_corpus.Solver(lvl)
        region = s.reachable(s.normalize(s.start_player, s.start_boxes), s.start_boxes)
        barrier = s.pi_corral(region, s.start_boxes)
        assert barrier is not None and len(barrier) >= 1
        assert barrier.issubset(s.start_boxes)

    def test_pi_corral_none_on_open_level(self):
        # Level 1 is open: the player can reach all non-box floor, so there is no corral.
        lvl = {x.n: x for x in xsb_levels.load_corpus()}[1]
        s = solve_corpus.Solver(lvl)
        region = s.reachable(s.normalize(s.start_player, s.start_boxes), s.start_boxes)
        assert s.pi_corral(region, s.start_boxes) is None


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
