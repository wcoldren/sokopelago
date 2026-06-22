"""Integration coverage for the curate/annotate pipeline: dedup, fail-closed ingest parsing,
bounded solver reuse, the additive annotated schema, and (when present) the calibration report.

Pure/in-memory except where it reads the committed Microban corpus; no network, no writes to
committed manifests (annotation runs ``write=False``)."""

import json

import annotate_corpus
import canonical
import ingest_corpus as ing
import scoring
import solve_corpus
import tiers
from xsb_levels import corpus_xsb, load_corpus, parse_levels


def _lvl(rows):
    return parse_levels("; 1\n\n" + "\n".join(rows))[0]


class TestDedupCanonical:
    def test_dihedral_and_player_shift_collapse_to_one_key(self):
        base = ("######", "#@ $.#", "#    #", "######")
        keys = set()
        grid = canonical.pad(base)
        for _ in range(4):
            for g in (grid, tuple(r[::-1] for r in grid)):
                keys.add(canonical.canonical_player_normalized(_lvl(g)))
            grid = canonical.rotate90(grid)
        # a player shifted elsewhere in the same reachable region is the SAME puzzle
        shifted = ("######", "#  $.#", "#@   #", "######")
        keys.add(canonical.canonical_player_normalized(_lvl(shifted)))
        assert len(keys) == 1

    def test_distinct_boards_differ(self):
        a = canonical.canonical_player_normalized(_lvl(("#####", "#@$.#", "#####")))
        b = canonical.canonical_player_normalized(_lvl(("######", "#@ $.#", "#.$  #", "######")))
        assert a != b

    def test_cross_corpus_dedup_drops_microban_duplicate(self):
        mb1 = load_corpus(corpus_xsb("microban"))[0]
        novel = ("#######", "#@ $ .#", "#  $ .#", "#######")
        kept, dropped = ing.dedup_levels([_lvl(mb1.rows), _lvl(novel)], against=("microban",))
        assert any(d["reason"].startswith("dup-vs-microban") for d in dropped)
        assert len(kept) == 1  # the novel one survives


class TestIngestParseFailClosed:
    def test_rejects_unrecognized_glyph(self):
        try:
            ing.parse_source("; 1\n\n####\n#1@#\n####\n")  # '1' is not a board glyph
        except ValueError:
            return
        raise AssertionError("near-board line with a stray glyph was not rejected")

    def test_parses_clean_xsb(self):
        text = "; 1\n\n#####\n#@$.#\n#####\n\n; 2\n\n######\n#@ $.#\n######\n"
        levels = ing.parse_source(text)
        assert len(levels) == 2 and all(l.boxes for l in levels)


class TestAnnotateBoundedSolve:
    def test_overbudget_level_marked_unsolved(self):
        # A multi-box level cannot solve under a 1-node budget -> unsolved, difficulty 1.0.
        rows = ["########", "#@ $ $ #", "#  $ $ #", "# .. ..#", "########"]
        saved = (solve_corpus.NODE_BUDGET, solve_corpus.SEARCH_PHASES)
        try:
            ref = annotate_corpus.microban_reference_bounds()
            res = annotate_corpus.parallel_annotate([(rows, {})], workers=1, node_budget=1,
                                                    wall_cap=30, ref_bounds=ref)
        finally:
            solve_corpus.NODE_BUDGET, solve_corpus.SEARCH_PHASES = saved
        assert res[0] is not None and res[0]["solved"] is False
        assert res[0]["base"]["difficulty"] == 1.0


class TestAnnotatedSchema:
    def test_microban_annotation_is_additive_and_valid(self):
        before = {e["n"]: e for e in json.loads((corpus_xsb("microban").parent.parent
                  / "apworld/sokopelago/data/microban.json").read_text())}
        entries, stats = annotate_corpus.annotate("microban", workers=1, write=False)
        assert stats["reused"] == 155 and stats["unsolved"] == 0  # authoritative fields reused
        new_keys = ("box_change_difficulty", "fun_features", "structural", "quality_score",
                    "canonical_hash", "provenance", "license")
        base_keys = ("n", "name", "board", "par", "difficulty", "solution", "solved", "optimal")
        diffs = []
        for e in entries:
            assert all(k in e for k in new_keys)
            assert 0.0 <= e["quality_score"] <= 1.0
            assert 0.0 <= e["fun_features"]["likeability"] <= 1.0
            assert e["provenance"] == "microban"
            for k in base_keys:  # additive: original fields untouched
                if k in before[e["n"]]:
                    assert e[k] == before[e["n"]][k]
            diffs.append(e["difficulty"])
        # difficulty stays on the absolute scale -> all three tiers present, cutoffs respected
        seen = {tiers.tier_of(d) for d in diffs}
        assert {"easy", "medium", "hard"} <= seen


class TestCalibrationReport:
    def test_report_shape_if_present(self):
        # The calibration dataset is dev-only/gitignored; only validate the report when it exists.
        from fetch_calibration import DEST_DIR

        report_path = DEST_DIR / "report.json"
        if not report_path.exists():
            import pytest

            pytest.skip("calibration report not generated (run tools/fetch_calibration.py + calibrate_scoring.py)")
        report = json.loads(report_path.read_text())
        assert "correlations_vs_like_rate" in report
        q = report["correlations_vs_like_rate"]["quality_score"]
        assert "rho" in q and "ci95" in q and "n" in q
        assert report["n_used"] >= 100
