"""Provenance registry + build-guard coverage (``tools/provenance.py``).

Asserts the machine-readable registry is complete and redistributable for every built-in corpus,
that the attribution markdown is a faithful render of it, and that the guard actually fails closed
on missing/incomplete entries."""

import provenance


class TestRegistryComplete:
    def test_builtins_complete_and_redistributable(self):
        provenance.assert_complete(["microban", "pullban", "autoban"])  # raises if not

    def test_pullban_and_autoban_are_original(self):
        reg = provenance.load_provenance()
        assert reg["pullban"]["original_by_construction"] is True
        assert reg["autoban"]["original_by_construction"] is True
        assert reg["microban"]["original_by_construction"] is False
        # pullban/autoban are original work -> NOT credited to Skinner
        assert "Skinner" not in reg["pullban"]["author"]
        assert "Skinner" not in reg["autoban"]["author"]
        assert reg["microban"]["author"] == "David W. Skinner"

    def test_every_registered_entry_validates(self):
        for name, prov in provenance.load_provenance().items():
            assert provenance.validate(prov) == [], f"{name} has provenance problems"


class TestGuardFailsClosed:
    def test_missing_entry_raises(self):
        try:
            provenance.assert_complete(["ghost"], provs={})
        except SystemExit:
            return
        raise AssertionError("missing provenance entry was not caught")

    def test_incomplete_entry_raises(self):
        bad = {"x": {"corpus": "x", "source_name": "X", "author": "", "license_id": "y",
                     "distribution_terms": "t", "redistributable": False}}
        problems = provenance.validate(bad["x"])
        assert any("author" in p for p in problems)
        assert any("redistributable" in p for p in problems)
        try:
            provenance.assert_complete(["x"], provs=bad)
        except SystemExit:
            return
        raise AssertionError("incomplete entry was not caught")


class TestAttributionRender:
    def test_committed_md_matches_registry(self):
        committed = provenance.ATTRIBUTION_PATH.read_text(encoding="utf-8")
        assert committed == provenance.render_attribution_md(provenance.load_provenance())
