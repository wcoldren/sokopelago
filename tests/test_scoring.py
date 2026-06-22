"""Unit coverage for the standalone scoring module (``tools/scoring.py``).

These exercise the scorer's pieces on tiny in-memory levels (plus a couple of real Microban
levels for shape/bounds) — fast, no file writes. The cross-corpus annotation integration is
covered separately in ``test_scoring_and_ingest.py``."""

import json

import scoring as s
import solve_corpus
from xsb_levels import corpus_xsb, load_corpus, manifest_json, parse_levels


def _lvl(rows):
    return parse_levels("; 1\n\n" + "\n".join(rows))[0]


class TestSolutionTrace:
    def test_box_switches_counted(self):
        # Two boxes already on goals but the corridor forces alternating manipulation; what we
        # assert is the mechanic: solving a 2-box level and counting attention switches works and
        # is bounded by the number of pushes.
        level = _lvl(("######", "#@$ .#", "# $ .#", "######"))
        e = solve_corpus.solve(level)
        assert e["solved"]
        pushed, states = s.trace_solution(level, e["solution"])
        assert len(pushed) == e["par"]  # one id per push
        switches = sum(1 for i in range(1, len(pushed)) if pushed[i] != pushed[i - 1])
        assert 0 <= switches <= max(0, len(pushed) - 1)
        assert len(states) == len(pushed)

    def test_single_box_never_switches(self):
        level = _lvl(("#####", "#@$.#", "#####"))
        e = solve_corpus.solve(level)
        pushed, _ = s.trace_solution(level, e["solution"])
        assert len(set(pushed)) == 1  # only one box exists -> no switching


class TestBoxChangeDifficulty:
    def test_bounded_and_monotone_in_switches(self):
        a = s.box_change_difficulty(0, par=10, nodes=100, boxes=2)
        b = s.box_change_difficulty(8, par=10, nodes=100, boxes=2)
        assert 0.0 <= a <= b <= 1.0

    def test_more_nodes_harder(self):
        lo = s.box_change_difficulty(2, par=10, nodes=10, boxes=2)
        hi = s.box_change_difficulty(2, par=10, nodes=1_000_000, boxes=2)
        assert lo < hi <= 1.0


class TestInvertedU:
    def test_peaks_at_moderate_challenge(self):
        trivial = s.likeability(0.0)
        moderate = s.likeability(1.0 - s.WEIGHTS["likeability_mu"])  # challenge that maxes the bump
        brutal = s.likeability(1.0)
        assert moderate > trivial and moderate > brutal  # inverted-U, not monotone
        assert moderate == max(s.likeability(c / 20) for c in range(21))


class TestStructural:
    def test_goal_room_connected_true_when_adjacent(self):
        solver = solve_corpus.Solver(_lvl(("######", "#@$..#", "######")))
        assert s.goal_room_connected(solver) is True

    def test_goal_room_connected_false_when_split(self):
        # Two goals separated by a wall pillar -> two goal clusters.
        solver = solve_corpus.Solver(_lvl(("#######", "#.#@#.#", "#  $  #", "#######")))
        assert s.goal_room_connected(solver) is False

    def test_openness_within_unit_range(self):
        solver = solve_corpus.Solver(_lvl(("######", "#@ $.#", "#    #", "######")))
        assert 0.0 <= s.openness(solver) <= 1.0


class TestScoreQuality:
    def test_thin_features_in_range(self):
        # The generator's hot-loop shape (no difficulty/likeability keys) still scores in [0,1].
        assert 0.0 <= s.score_quality({"par": 12.0, "boxes": 3.0, "moves": 40.0}) <= 1.0

    def test_rich_features_use_components(self):
        low = s.score_quality({"difficulty": 0.1, "box_change_difficulty": 0.1, "likeability": 0.1, "structural_elegance": 0.1})
        high = s.score_quality({"difficulty": 0.6, "box_change_difficulty": 0.6, "likeability": 0.9, "structural_elegance": 0.9})
        assert 0.0 <= low < high <= 1.0


class TestComputeFeaturesShape:
    def _microban(self):
        levels = {l.n: l for l in load_corpus(corpus_xsb("microban"))}
        data = {e["n"]: e for e in json.loads(manifest_json("microban").read_text())}
        return levels, data

    def test_additive_subobject_shape_and_bounds(self):
        levels, data = self._microban()
        for n in (1, 30, 78, 144):
            f = s.compute_features(levels[n], data[n])
            assert set(f) == {"box_change_difficulty", "fun_features", "structural", "quality_score", "canonical_hash"}
            assert 0.0 <= f["box_change_difficulty"] <= 1.0
            assert 0.0 <= f["quality_score"] <= 1.0
            ff = f["fun_features"]
            assert set(ff) == {"playable_area", "openness", "boxes", "steps_per_box", "search_difficulty", "likeability"}
            assert 0.0 <= ff["openness"] <= 1.0 and 0.0 <= ff["likeability"] <= 1.0
            st = f["structural"]
            assert set(st) == {"goal_room_connected", "matter_fraction", "matter_method", "dead_floor_ratio", "box_density", "deadlock_proximity"}
            assert 0.0 <= st["matter_fraction"] <= 1.0 and 0.0 <= st["deadlock_proximity"] <= 1.0
            assert len(f["canonical_hash"]) == 16

    def test_unsolved_falls_back_to_geometry(self):
        levels, _ = self._microban()
        f = s.compute_features(levels[1], {"solved": False, "boxes": len(levels[1].boxes)})
        assert f["box_change_difficulty"] == 1.0
        assert f["structural"]["matter_method"] == "off-goal-start"
        assert f["structural"]["deadlock_proximity"] == 0.0
        assert 0.0 <= f["quality_score"] <= 1.0
