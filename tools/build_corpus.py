#!/usr/bin/env python3
"""Offline data-prep: build the geometry/names fields of the level manifest.

Parses the canonical corpus ``levels/microban.xsb`` (via the shared ``xsb_levels``
parser, so level splitting / numbering matches the client and the solver) and writes
the ``{"n", "name", "board"}`` fields of ``apworld/sokopelago/data/microban.json``.
``board`` is the raw XSB rows, bundled so the client renders from this one manifest
instead of also fetching the ``.xsb`` (which stays the canonical authoring source).

The enriched solver fields (par / solution / difficulty) are produced by
``tools/solve_corpus.py`` — the canonical manifest producer. This tool **merges**:
it refreshes ``n``/``name``/``board`` while preserving any existing solver fields, so
running it never downgrades an enriched manifest. It NEVER solves Sokoban; it only reads
geometry and titles.

Run:  python tools/build_corpus.py
"""

from __future__ import annotations

import argparse
import json

import provenance
from xsb_levels import REPO_ROOT, corpus_xsb, load_corpus, manifest_json
from xsb_levels import parse_levels as _parse_full


def parse_levels(text: str) -> list[dict[str, object]]:
    """Return [{"n": int, "name": str, "board": list[str]}, ...] in corpus order."""
    return [{"n": lvl.n, "name": lvl.name, "board": list(lvl.rows)} for lvl in _parse_full(text)]


def merge_boards(name: str) -> list[dict[str, object]]:
    """Refresh ``n``/``name``/``board`` in ``name``'s manifest from the canonical XSB,
    preserving any existing solver fields, and return the entries. Reused by
    ``tools/generate_corpus.py`` to bundle boards after the solver pass."""
    provenance.require(name)  # no manifest without a recorded, redistributable source
    out = manifest_json(name)
    levels = load_corpus(corpus_xsb(name))
    existing: dict[int, dict[str, object]] = {}
    if out.exists():
        existing = {entry["n"]: entry for entry in json.loads(out.read_text(encoding="utf-8"))}

    entries: list[dict[str, object]] = []
    for lvl in levels:
        merged = dict(existing.get(lvl.n, {}))  # keep any solver fields
        merged["n"] = lvl.n
        merged["name"] = lvl.name
        merged["board"] = list(lvl.rows)
        entries.append(merged)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} levels -> {out.relative_to(REPO_ROOT)}")
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="microban", help="corpus name (default: microban)")
    merge_boards(ap.parse_args().corpus)


if __name__ == "__main__":
    main()
