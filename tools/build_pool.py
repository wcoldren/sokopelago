#!/usr/bin/env python3
"""Merge selected corpora into ONE re-indexed corpus the apworld can use as a single pool.

The apworld selects a seed's levels from one corpus (``data/<name>.json``); this builds such a
corpus by combining levels from several committed sets, re-indexed to contiguous ``n=1..N`` (which
the location-id map now supports past 155 — see ``corpus.LOCATION_MAX``). Re-run with different
filters to try different pools, then point a YAML's ``corpus:`` at it.

Difficulty is already on the shared Microban scale across all sets, so the merged pool is coherent.
Each level keeps its annotation fields and gains a ``source`` ("origcorpus:n") + a readable ``name``
("Sasquatch III 17") so the client shows provenance.

Run:  python tools/build_pool.py                                   # all solved levels -> curated.json
      python tools/build_pool.py --corpora microban2,microban3 --max-difficulty easy_medium
      python tools/build_pool.py --name hardpool --max-boxes 8 --limit 150
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "apworld", "sokopelago"))

import canonical
import tiers

DATA_DIR = os.path.join(_HERE, "..", "apworld", "sokopelago", "data")
ALL_CORPORA = (
    ["microban", "pullban", "autoban", "microban2", "microban3"]
    + [f"sasquatch{i}" for i in range(1, 10)]
    + ["xsokoban90"]
)
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
# Carried through to the merged manifest so consumers keep working unchanged.
_KEEP = (
    "board",
    "par",
    "moves",
    "solution",
    "boxes",
    "search_nodes",
    "difficulty",
    "optimal",
    "solved",
    "solver",
    "requires_pull",
    "box_change_difficulty",
    "fun_features",
    "structural",
    "quality_score",
    "canonical_hash",
)


def _label(corpus: str) -> str:
    if corpus.startswith("sasquatch"):
        return f"Sasquatch {_ROMAN[int(corpus[len('sasquatch') :])]}"
    return {
        "microban": "Microban",
        "microban2": "Microban II",
        "microban3": "Microban III",
        "pullban": "Pullban",
        "autoban": "Autoban",
        "xsokoban90": "XSokoban",
    }.get(corpus, corpus)


def gather(args) -> list[dict]:
    ceiling = tiers.MAX_DIFFICULTY_CEILING[args.max_difficulty]
    rows = []
    for corpus in args.corpora:
        for e in json.loads(open(os.path.join(DATA_DIR, f"{corpus}.json")).read()):
            if args.solved_only and not e.get("solved"):
                continue
            # Drop pull-required levels by default: a merged pool that ships with pull_logic off
            # (e.g. curated) would otherwise contain levels AP's fill treats as push-solvable when
            # they aren't, leaving the seed unwinnable on a pure-push run. --keep-pull retains them
            # for experiments (only sound when the consuming YAML turns pull_logic on).
            if not args.keep_pull and e.get("requires_pull"):
                continue
            if not tiers.within_cap(float(e.get("difficulty", 1.0)), ceiling):
                continue
            boxes = (e.get("fun_features") or {}).get("boxes", e.get("boxes"))
            if args.max_boxes and boxes and boxes > args.max_boxes:
                continue
            rows.append({"_corpus": corpus, "_orig_n": e["n"], "_origname": e.get("name", str(e["n"])), **e})
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen, kept = set(), []
    for r in rows:
        key = canonical.canonical(tuple(r["board"]))
        if key not in seen:
            seen.add(key)
            kept.append(r)
    return kept


def stride_sample(rows: list[dict], limit: int) -> list[dict]:
    """Keep ``limit`` levels evenly across the (already difficulty-sorted) list, so the pool keeps
    its full easy->hard range rather than just the easiest ``limit``."""
    if limit <= 0 or limit >= len(rows):
        return rows
    step = len(rows) / limit
    return [rows[int(i * step)] for i in range(limit)]


def build(args) -> dict:
    rows = gather(args)
    if args.dedup:
        rows = dedupe(rows)
    rows.sort(key=lambda r: (float(r.get("difficulty", 1.0)), r["_corpus"], r["_orig_n"]))  # easy->hard
    rows = stride_sample(rows, args.limit)

    entries = []
    for i, r in enumerate(rows, start=1):
        entry = {"n": i, "name": f"{_label(r['_corpus'])} {r['_origname']}", "source": f"{r['_corpus']}:{r['_orig_n']}"}
        for k in _KEEP:
            if k in r:
                entry[k] = r[k]
        entries.append(entry)

    out = os.path.join(DATA_DIR, f"{args.name}.json")
    open(out, "w").write(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    t = {k: sum(1 for e in entries if tiers.tier_of(e["difficulty"]) == k) for k in ("easy", "medium", "hard")}
    meta = {
        "name": args.name,
        "count": len(entries),
        "tiers": t,
        "filter": {
            "corpora": args.corpora,
            "solved_only": args.solved_only,
            "max_difficulty": args.max_difficulty,
            "max_boxes": args.max_boxes,
            "limit": args.limit,
            "dedup": args.dedup,
            "keep_pull": args.keep_pull,
        },
    }
    open(os.path.join(_HERE, "..", "levels", f"{args.name}.pool.json"), "w").write(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {len(entries)} levels -> apworld/sokopelago/data/{args.name}.json")
    print(f"  tiers: easy {t['easy']} / medium {t['medium']} / hard {t['hard']}")
    print(
        "  sources: "
        + ", ".join(
            f"{c}×{sum(1 for e in entries if e['source'].startswith(c + ':'))}"
            for c in args.corpora
            if any(e["source"].startswith(c + ":") for e in entries)
        )
    )
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default="curated", help="output corpus name -> data/<name>.json")
    ap.add_argument("--corpora", default=",".join(ALL_CORPORA), help="comma list to merge")
    ap.add_argument("--max-difficulty", default="any", choices=["any", "easy", "easy_medium"])
    ap.add_argument("--max-boxes", type=int, default=0, help="drop levels with more boxes (0 = no cap)")
    ap.add_argument("--limit", type=int, default=0, help="cap to N levels, sampled across difficulty (0 = all)")
    ap.add_argument(
        "--include-unsolved",
        dest="solved_only",
        action="store_false",
        help="include unsolved (no solution/par/hints) levels",
    )
    ap.add_argument("--no-dedup", dest="dedup", action="store_false", help="skip dihedral dedup")
    ap.add_argument(
        "--keep-pull",
        action="store_true",
        help="retain pull-required levels (default: exclude; only sound with pull_logic on)",
    )
    ap.set_defaults(solved_only=True, dedup=True, keep_pull=False)
    args = ap.parse_args()
    args.corpora = [c for c in args.corpora.split(",") if c]
    build(args)


if __name__ == "__main__":
    main()
