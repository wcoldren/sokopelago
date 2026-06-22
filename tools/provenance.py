#!/usr/bin/env python3
"""Machine-readable per-corpus provenance / license registry + a build-time completeness gate.

Every corpus the toolchain builds a manifest for must have a redistributable provenance entry
in ``levels/provenance.json`` — author, license id, the verbatim distribution terms, and the
required attribution. The build refuses to write a manifest for a corpus that lacks one
(:func:`require`, wired into ``build_corpus.merge_boards`` and
``solve_corpus.build_corpus_manifest``), so no level can ship without a recorded source.

``levels/ATTRIBUTION.md`` is a *generated* artifact: :func:`render_attribution_md` renders it
deterministically from this registry, and a test asserts the committed file matches (so the two
can never drift). The structured registry is the single source of truth; the markdown is a view.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypedDict

from xsb_levels import REPO_ROOT

PROVENANCE_PATH = REPO_ROOT / "levels" / "provenance.json"
ATTRIBUTION_PATH = REPO_ROOT / "levels" / "ATTRIBUTION.md"


class Provenance(TypedDict, total=False):
    corpus: str
    source_name: str
    author: str
    source_url: str | None
    license_id: str
    license_url: str | None
    distribution_terms: str  # verbatim permission text
    attribution_required: str | None  # the credit line that must travel with the levels
    redistributable: bool  # the gate: a non-redistributable set may never be shipped/built
    original_by_construction: bool  # original work (no third-party authorship to credit)
    notes: str | None
    retrieved_utc: str | None  # stamped by ingest at fetch time
    sha256_xsb: str | None  # digest of levels/<corpus>.xsb as ingested


# Fields a complete, shippable entry must carry. ``original_by_construction`` sets may legitimately
# have no external ``source_url``, so it is not required.
_REQUIRED_TEXT_FIELDS = ("corpus", "source_name", "author", "license_id", "distribution_terms")


def load_provenance(path: Path = PROVENANCE_PATH) -> dict[str, Provenance]:
    """The full registry, keyed by corpus name (file order preserved)."""
    if not path.exists():
        raise SystemExit(f"provenance registry not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def provenance_for(name: str, provs: dict[str, Provenance] | None = None) -> Provenance | None:
    return (provs if provs is not None else load_provenance()).get(name)


def validate(prov: Provenance) -> list[str]:
    """Problems that make an entry unfit to ship, as human-readable strings (empty == OK)."""
    problems: list[str] = []
    for field in _REQUIRED_TEXT_FIELDS:
        if not str(prov.get(field) or "").strip():
            problems.append(f"missing/empty '{field}'")
    if prov.get("redistributable") is not True:
        problems.append("not marked redistributable (redistributable != true)")
    if not prov.get("original_by_construction") and not str(prov.get("attribution_required") or "").strip():
        problems.append("third-party set without 'attribution_required'")
    return problems


def assert_complete(names, provs: dict[str, Provenance] | None = None) -> None:
    """Raise ``SystemExit`` if any of ``names`` lacks a complete, redistributable entry,
    listing every problem found. Used as the whole-set guard (e.g. over ``CORPORA``)."""
    registry = provs if provs is not None else load_provenance()
    failures: list[str] = []
    for name in names:
        prov = registry.get(name)
        if prov is None:
            failures.append(f"{name}: no provenance entry in {PROVENANCE_PATH.name}")
            continue
        failures += [f"{name}: {p}" for p in validate(prov)]
    if failures:
        raise SystemExit("provenance check failed:\n  " + "\n  ".join(failures))


def require(name: str, provs: dict[str, Provenance] | None = None) -> Provenance:
    """Return ``name``'s entry or raise — the per-corpus gate the manifest builders call first."""
    assert_complete([name], provs)
    prov = (provs if provs is not None else load_provenance())[name]
    return prov


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert(name: str, prov: Provenance, path: Path = PROVENANCE_PATH) -> None:
    """Insert or replace ``name``'s entry and rewrite the registry (used by ingest)."""
    registry = load_provenance(path) if path.exists() else {}
    registry[name] = prov
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# ATTRIBUTION.md is rendered from the registry (single source of truth)
# --------------------------------------------------------------------------------------
def _render_entry(prov: Provenance) -> str:
    lines = [f"## {prov['source_name']} — `{prov['corpus']}.xsb`", ""]
    lines.append(f"- **Author:** {prov['author']}")
    if prov.get("source_url"):
        lines.append(f"- **Source:** <{prov['source_url']}>")
    lines.append(f"- **License:** `{prov['license_id']}`"
                 + (f" (<{prov['license_url']}>)" if prov.get("license_url") else ""))
    if prov.get("original_by_construction"):
        lines.append("- **Original by construction** — no third-party puzzles; no external attribution required.")
    lines += ["", "### Distribution terms", "", f"> {prov['distribution_terms']}", ""]
    if prov.get("attribution_required"):
        lines += [f"Required credit: *{prov['attribution_required']}*", ""]
    if prov.get("notes"):
        lines += [prov["notes"], ""]
    if prov.get("sha256_xsb"):
        lines += [f"`sha256(levels/{prov['corpus']}.xsb)` = `{prov['sha256_xsb']}`", ""]
    return "\n".join(lines)


def render_attribution_md(provs: dict[str, Provenance]) -> str:
    """The full ``levels/ATTRIBUTION.md`` body, deterministic in registry (file) order."""
    head = [
        "<!-- GENERATED FILE — do not edit by hand.",
        "     Rendered from levels/provenance.json by tools/provenance.py",
        "     (regenerate: python tools/provenance.py --write-attribution). -->",
        "",
        "# Level corpus attribution",
        "",
        "Per-set provenance and redistribution terms for every bundled Sokoban corpus. The",
        "machine-readable source of truth is [`provenance.json`](provenance.json); this file is",
        "generated from it. A repo-level summary lives in [`../CREDITS.md`](../CREDITS.md).",
        "",
    ]
    body = "\n\n".join(_render_entry(p).rstrip() for p in provs.values())
    return "\n".join(head) + "\n" + body + "\n"


def write_attribution_md(path: Path = ATTRIBUTION_PATH) -> None:
    path.write_text(render_attribution_md(load_provenance()), encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)} from {PROVENANCE_PATH.name}")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-attribution", action="store_true", help="regenerate levels/ATTRIBUTION.md")
    ap.add_argument("--check", action="store_true", help="assert every entry is complete & redistributable")
    args = ap.parse_args()
    if args.check:
        assert_complete(list(load_provenance().keys()))
        print("provenance OK")
    if args.write_attribution:
        write_attribution_md()
    if not (args.check or args.write_attribution):
        ap.print_help()


if __name__ == "__main__":
    main()
