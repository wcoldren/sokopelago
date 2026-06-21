import json
from pathlib import Path

import build_corpus
import layout
import solve_corpus
import tiers
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
        assert levels[0]["board"] == ["#####", "#@$.#", "#####"]

    def test_every_entry_bundles_its_board(self):
        # The client renders from the manifest's bundled board, so each entry's board
        # must match the canonical corpus rows verbatim (a stale rebuild fails here).
        data = {e["n"]: e for e in json.loads(MANIFEST.read_text())}
        levels = {lvl.n: lvl for lvl in xsb_levels.load_corpus()}
        assert set(data) == set(levels)
        for n, lvl in levels.items():
            assert data[n].get("board") == list(lvl.rows), f"level {n} board mismatch"


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


class TestDifficultyDistribution:
    """Difficulty is an *absolute* log-scaled score (not even thirds): "easy" must mean a
    genuinely simple puzzle. The original bug — one external-solved outlier pinning the
    min-max scale so 154/155 levels read as 'easy' — must not recur, but the honest
    distribution is legitimately medium-heavy."""

    def _tiers(self, diffs):
        easy = sum(tiers.tier_of(d) == "easy" for d in diffs)
        hard = sum(tiers.tier_of(d) == "hard" for d in diffs)
        return easy, len(diffs) - easy - hard, hard

    def test_committed_manifest_populates_every_tier(self):
        data = json.loads(MANIFEST.read_text())
        diffs = [e["difficulty"] for e in data]
        easy, med, hard = self._tiers(diffs)
        # Every tier non-empty, and "easy" is a sane minority of genuinely simple levels
        # (not the degenerate 154/0/1, and not a flat third either).
        assert easy and med and hard, f"a tier is empty: easy={easy} med={med} hard={hard}"
        assert 20 <= easy <= 70, f"easy tier count out of expected range: {easy}"
        # The hardest level (153, external-solved) sits in the hard tier, not 'easy'.
        worst = max(data, key=lambda e: e["difficulty"])
        assert tiers.tier_of(worst["difficulty"]) == "hard"

    def test_attach_difficulty_is_monotonic_and_outlier_topped(self):
        # A ramp of ordinary levels plus one runaway (huge par/nodes). The absolute score
        # must rank heavier levels higher and put the outlier on top — without the old
        # min-max collapse that flattened the ramp to a single value.
        entries = [
            {"n": i, "solved": True, "par": i, "moves": 2 * i, "boxes": 1 + i // 10, "_nodes": i * i}
            for i in range(1, 31)
        ]
        entries.append({"n": 99, "solved": True, "par": 100000, "moves": 100000, "boxes": 9, "_nodes": 6_000_000})
        solve_corpus._attach_difficulty(entries)
        ramp = [e for e in entries if e["n"] != 99]
        scores = [e["difficulty"] for e in ramp]
        assert scores == sorted(scores), "ramp difficulty is not monotonic in the signals"
        assert len(set(scores)) > 1, "ramp collapsed to a single difficulty (outlier crush)"
        assert max(entries, key=lambda e: e["difficulty"])["n"] == 99  # runaway is hardest
        assert all(0.0 <= e["difficulty"] <= 1.0 for e in entries)
        # _nodes is consumed into the persisted search_nodes (so a re-score can reuse it).
        assert all("search_nodes" in e and "_nodes" not in e for e in entries)

    def test_rescore_reads_persisted_search_nodes(self):
        # A re-score has no live _nodes; _attach_difficulty must fall back to search_nodes
        # and leave it intact (no re-solve).
        entries = [
            {"n": 1, "solved": True, "par": 5, "moves": 5, "boxes": 1, "search_nodes": 10},
            {"n": 2, "solved": True, "par": 50, "moves": 60, "boxes": 3, "search_nodes": 9999},
        ]
        solve_corpus._attach_difficulty(entries)
        assert entries[1]["difficulty"] > entries[0]["difficulty"]  # heavier level outranks
        assert entries[0]["search_nodes"] == 10 and entries[1]["search_nodes"] == 9999
        assert entries[0]["search_nodes"] == 10 and entries[1]["search_nodes"] == 9999


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


class TestPullSolver:
    """The pull-aware solver mode (Phase 5 expert tier): pulls solve configurations that
    pure pushing can't, and the solver flags which levels genuinely *require* a pull."""

    def _level(self, board: str):
        return xsb_levels.parse_levels(f"; t\n\n{board}")[0]

    # A box pinned against the left wall: no cell to stand on its far side, so it can't be
    # pushed toward the goal at all — but it can be pulled out. So the level REQUIRES pull.
    PULL_REQUIRED = "#####\n#$ .#\n#@  #\n#####"
    PUSH_OK = "#####\n#@$.#\n#####"

    def test_push_only_cannot_solve_a_pull_level(self):
        assert solve_corpus.push_solvable(self._level(self.PULL_REQUIRED)) is False

    def test_pull_mode_solves_and_flags_requires_pull(self):
        e = solve_corpus.solve_pull(self._level(self.PULL_REQUIRED))
        assert e["solved"] is True
        assert e["requires_pull"] is True
        assert "P" in e["solution"]  # the recorded solution uses at least one pull

    def test_pull_solution_replays_to_a_win(self):
        lvl = self._level(self.PULL_REQUIRED)
        e = solve_corpus.solve_pull(lvl)
        assert solve_corpus.replay(lvl, e["solution"]) is True

    def test_push_solvable_level_is_not_flagged_requires_pull(self):
        lvl = self._level(self.PUSH_OK)
        assert solve_corpus.push_solvable(lvl) is True
        e = solve_corpus.solve_pull(lvl)
        assert e["solved"] is True and e["requires_pull"] is False

    def test_pull_marker_replays(self):
        # Box at (1,1) pinned on the left wall; goal at (2,1) where the player starts. A
        # single pull-right ("PR") drags the box onto the goal.
        lvl = self._level("#####\n#$+ #\n#####")
        assert solve_corpus.replay(lvl, "PR") is True
        assert solve_corpus.replay(lvl, "r") is False  # a bare walk never wins it


class TestPullbanManifest:
    """The original Phase 5 expert corpus: a mix of push hosts (which carry the shuffled
    Pull item) and pull-gated levels, all replay-verified, each board bundled."""

    PULLBAN = ROOT / "apworld/sokopelago/data/pullban.json"

    def _levels(self):
        return {lvl.n: lvl for lvl in xsb_levels.load_corpus(xsb_levels.corpus_xsb("pullban"))}

    def test_all_solved_with_boards(self):
        data = json.loads(self.PULLBAN.read_text())
        assert len(data) >= 8
        assert all(e["solved"] for e in data)
        assert all("board" in e for e in data)

    def test_has_both_pull_and_host_levels(self):
        data = json.loads(self.PULLBAN.read_text())
        pull = [e for e in data if e.get("requires_pull")]
        hosts = [e for e in data if not e.get("requires_pull")]
        # Gated levels make the tier meaningful; hosts give the Pull item a reachable home.
        assert pull, "no pull-gated levels"
        assert hosts, "no push-solvable host levels (Pull item would be unplaceable)"

    def test_corpus_is_host_heavy_for_fillability(self):
        # The 0.7.1 expansion keeps the pull-gated fraction well under half so pull seeds have
        # plenty of host locations and fill reliably (a high pull ratio starves the filler).
        data = json.loads(self.PULLBAN.read_text())
        assert len(data) >= 24, "expanded pull corpus should be sizable"
        pull_fraction = sum(bool(e.get("requires_pull")) for e in data) / len(data)
        assert pull_fraction < 0.5, f"pull-gated fraction {pull_fraction:.2f} too high for robust fills"

    def test_solutions_replay(self):
        data = {e["n"]: e for e in json.loads(self.PULLBAN.read_text())}
        for n, lvl in self._levels().items():
            assert solve_corpus.replay(lvl, data[n]["solution"]), f"level {n} solution does not solve it"

    def test_gated_levels_are_push_unsolvable(self):
        # The gate is solver-proven: a requires_pull level has no pure push solution.
        levels = self._levels()
        data = {e["n"]: e for e in json.loads(self.PULLBAN.read_text())}
        for n in levels:
            if data[n].get("requires_pull"):
                assert solve_corpus.push_solvable(levels[n]) is False, f"level {n} is actually push-solvable"


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


class TestEscapeValveCounts:
    def test_all_fit_when_budget_is_ample(self):
        counts = layout.escape_valve_counts(20, {"skip": 3, "hint": 3, "undo": 5, "trap": 2})
        assert counts == {"skip": 3, "hint": 3, "undo": 5, "trap": 2}

    def test_priority_drops_traps_then_undo_then_hint(self):
        # budget 4, requests 2 each: skip and hint fill first (priority), then undo.
        counts = layout.escape_valve_counts(4, {"skip": 2, "hint": 2, "undo": 2, "trap": 2})
        assert counts == {"skip": 2, "hint": 2, "undo": 0, "trap": 0}
        assert sum(counts.values()) == 4

    def test_skip_survives_a_budget_of_one(self):
        counts = layout.escape_valve_counts(1, {"skip": 3, "hint": 3, "undo": 3, "trap": 3})
        assert counts == {"skip": 1, "hint": 0, "undo": 0, "trap": 0}

    def test_zero_budget_yields_nothing(self):
        counts = layout.escape_valve_counts(0, {"skip": 3, "hint": 3, "undo": 3, "trap": 3})
        assert counts == {"skip": 0, "hint": 0, "undo": 0, "trap": 0}


class TestAssignLevelsByDifficulty:
    def _difficulty(self, n):
        # monotonic ramp: level k is harder than level k-1.
        return {k: k / 100 for k in range(1, n + 1)}

    def test_matches_chunk_shape(self):
        levels = list(range(1, 31))
        worlds = layout.assign_levels_by_difficulty(levels, self._difficulty(30), 10)
        assert [len(w) for w in worlds] == [len(w) for w in layout.chunk_levels(30, 10)]

    def test_every_level_placed_exactly_once(self):
        levels = list(range(1, 26))
        worlds = layout.assign_levels_by_difficulty(levels, self._difficulty(25), 10)
        flat = [n for w in worlds for n in w]
        assert sorted(flat) == levels

    def test_balances_difficulty_across_worlds(self):
        # A monotonic ramp chunked sequentially puts all the hard levels in the last
        # world; balancing should spread them so per-world means are close together.
        levels = list(range(1, 31))
        diff = self._difficulty(30)
        worlds = layout.assign_levels_by_difficulty(levels, diff, 10)
        means = [sum(diff[n] for n in w) / len(w) for w in worlds]
        assert max(means) - min(means) < 0.05

    def test_each_world_is_easiest_first(self):
        levels = list(range(1, 31))
        diff = self._difficulty(30)
        worlds = layout.assign_levels_by_difficulty(levels, diff, 10)
        for w in worlds:
            assert w == sorted(w, key=lambda n: diff[n])
