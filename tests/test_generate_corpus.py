"""Unit coverage for the owned puzzle generator (``tools/generate_corpus.py``).

These exercise the generator's logic directly (construction, dedup, scoring, the
generate loop) on tiny in-memory runs — fast, no file writes. The *committed* ``autoban``
corpus is validated separately by ``TestAutobanManifest`` in
``test_corpus_and_layout.py``."""

import random

import generate_corpus as g
import solve_corpus
import tiers


def _ref():
    return solve_corpus._calibration_bounds("autoban")


class TestCanonicalDedup:
    def test_dihedral_invariant(self):
        # A board and all 8 of its rotations/reflections share one canonical key.
        rows = ("######", "#@$ .#", "# $. #", "######")
        base = g.canonical(rows)
        grid = g._pad(rows)
        forms = []
        for _ in range(4):
            forms.append(tuple(grid))
            forms.append(tuple(r[::-1] for r in grid))
            grid = g._rotate90(grid)
        assert {g.canonical(f) for f in forms} == {base}

    def test_distinguishes_different_boards(self):
        a = ("#####", "#@$.#", "#####")
        b = ("#####", "#@ .#", "#$###", "#####")
        assert g.canonical(a) != g.canonical(b)

    def test_seen_from_corpora_nonempty(self):
        # Cross-corpus dedup seed: every Microban level contributes a canonical form.
        seen = g.seen_from_corpora(("microban",))
        assert len(seen) >= 155


class TestConstruction:
    def test_candidates_are_solvable_by_construction(self):
        # The core invariant: reverse-pull construction yields push-solvable levels. Solve
        # and replay each — 100% must win.
        g._apply_scoring_caps(300_000)
        rng = random.Random(11)
        checked = 0
        for _ in range(40):
            rows = g.construct_candidate(rng, g.TIER_SPECS["medium"])
            if rows is None:
                continue
            lvl = g.parse_levels("; 1\n\n" + "\n".join(rows))[0]
            e = solve_corpus.solve(lvl)
            assert e.get("solved"), "unsolvable candidate:\n" + "\n".join(rows)
            assert solve_corpus.replay(lvl, e["solution"]), "solution does not replay"
            checked += 1
        assert checked >= 10, "construction rejected too much to be meaningful"

    def test_prefilter_rejects_solved_state(self):
        # A board already on its goals (no scatter) must be pre-filtered out.
        rows = ("#####", "#@*.#", "#####")
        lvl = g.parse_levels("; 1\n\n" + "\n".join(rows))[0]
        solver = solve_corpus.Solver(lvl)
        assert g.prefilter(solver, solver.start_boxes) is False


class TestScoringCap:
    def test_node_budget_discards_overbudget(self):
        # With an absurdly tiny node budget, a non-trivial level cannot solve in time and is
        # discarded (returns None) rather than blocking the run.
        rows = ("########", "#@ $ $ #", "#  $ $ #", "# .. ..#", "########")
        tiny = g.parallel_score([tuple(rows)], workers=1, node_budget=1, wall_cap=30, ref_bounds=_ref())
        assert tiny == [None]

    def test_score_quality_in_unit_range(self):
        v = g.score_quality({"par": 12.0, "boxes": 3.0, "moves": 40.0})
        assert 0.0 <= v <= 1.0


class TestGenerateLoop:
    def _run(self, seed, workers):
        rng = random.Random(seed)
        seen = g.seen_from_corpora(("microban", "pullban"))
        kept, _ = g.generate(
            rng,
            {"easy": 3, "medium": 3, "hard": 0},
            node_budget=120_000,
            wall_cap=60,
            workers=workers,
            ref_bounds=_ref(),
            seen=seen,
            attempt_budget=20_000,
            time_budget=120,
            log=lambda *_: None,
        )
        return kept

    def test_meets_quotas_and_tiers_are_correct(self):
        kept = self._run(0, 1)
        assert len(kept["easy"]) == 3 and len(kept["medium"]) == 3
        for tier in ("easy", "medium"):
            for r in kept[tier]:
                assert tiers.tier_of(float(r["difficulty"])) == tier

    def test_no_dihedral_duplicates_in_run(self):
        kept = self._run(0, 1)
        canons = [r["canon"] for t in g.TIER_NAMES for r in kept[t]]
        assert len(canons) == len(set(canons))
        existing = g.seen_from_corpora(("microban", "pullban"))
        assert all(c not in existing for c in canons)

    def test_deterministic_across_seed_and_workers(self):
        def sig(kept):
            return [tuple(r["rows"]) for r in g.ordered_levels(kept)]

        a = sig(self._run(0, 1))
        assert a == sig(self._run(0, 1))  # repeatable
        assert a == sig(self._run(0, 4))  # worker-count independent
        assert a != sig(self._run(1, 1))  # seed actually varies the pack
