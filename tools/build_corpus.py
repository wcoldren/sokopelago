#!/usr/bin/env python3
"""Offline data-prep: build the names-only level manifest.

Parses the canonical corpus ``levels/microban.xsb`` (via the shared ``xsb_levels``
parser, so level splitting / numbering matches the client and the solver) and writes
the ``{"n", "name"}`` fields of ``apworld/sokopelago/data/microban.json``.

The enriched solver fields (par / solution / difficulty) are produced by
``tools/solve_corpus.py`` — the canonical manifest producer. This tool **merges**:
it refreshes ``n``/``name`` while preserving any existing solver fields, so running it
never downgrades an enriched manifest. It NEVER solves Sokoban; it only reads geometry
and titles.

Run:  python tools/build_corpus.py
"""

from __future__ import annotations

import json

from xsb_levels import REPO_ROOT, load_corpus
from xsb_levels import parse_levels as _parse_full

OUT = REPO_ROOT / "apworld" / "sokopelago" / "data" / "microban.json"


def parse_levels(text: str) -> list[dict[str, object]]:
    """Return [{"n": int, "name": str}, ...] in corpus order."""
    return [{"n": lvl.n, "name": lvl.name} for lvl in _parse_full(text)]


def main() -> None:
    levels = load_corpus()
    existing: dict[int, dict[str, object]] = {}
    if OUT.exists():
        existing = {entry["n"]: entry for entry in json.loads(OUT.read_text(encoding="utf-8"))}

    out: list[dict[str, object]] = []
    for lvl in levels:
        merged = dict(existing.get(lvl.n, {}))  # keep any solver fields
        merged["n"] = lvl.n
        merged["name"] = lvl.name
        out.append(merged)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} levels -> {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
