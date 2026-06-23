#!/usr/bin/env python3
"""Summary statistics + per-set breakdown across every bundled corpus manifest.

Loads each ``apworld/sokopelago/data/<corpus>.json``, fills in any missing scoring features on
the fly (the original microban/pullban/autoban manifests carry only base fields), and reports —
per set, split into levels WITH solutions (solved) and WITHOUT (geometry-only) — difficulty, the
quality/"fun" score, likeability, structure, size, and solve-method mix. Emits Markdown.

Run:  python tools/corpus_stats.py            # print report
      python tools/corpus_stats.py > out.md   # save it
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apworld", "sokopelago"))

import scoring
import tiers
from xsb_levels import REPO_ROOT, corpus_xsb, load_corpus, manifest_json

# Stable display order: the shipped reference corpora, then the curated additions.
ORDER = [
    "microban",
    "pullban",
    "autoban",
    "microban2",
    "microban3",
    *[f"sasquatch{i}" for i in range(1, 10)],
    "xsokoban90",
]


def _all_corpora() -> list[str]:
    names = {os.path.basename(p)[:-5] for p in glob.glob(str(REPO_ROOT / "apworld/sokopelago/data/*.json"))}
    return [n for n in ORDER if n in names] + sorted(names - set(ORDER))


def _enrich(name: str) -> list[dict]:
    """Manifest entries with scoring features guaranteed present (computed if the manifest, e.g.
    the original corpora, predates annotation)."""
    levels = {lv.n: lv for lv in load_corpus(corpus_xsb(name))}
    entries = json.loads(manifest_json(name).read_text(encoding="utf-8"))
    for e in entries:
        if "quality_score" not in e and e["n"] in levels:
            e.update(scoring.compute_features(levels[e["n"]], e))
    return entries


def _s(xs: list[float], fmt: str = ".2f") -> str:
    """min / median / mean / max of a numeric column."""
    if not xs:
        return "—"
    return f"{min(xs):{fmt}} / {st.median(xs):{fmt}} / {st.fmean(xs):{fmt}} / {max(xs):{fmt}}"


def _ff(e: dict, *keys: str):
    cur = e
    for k in keys:
        cur = (cur or {}).get(k) if isinstance(cur, dict) else None
    return cur


def _method(e: dict) -> str:
    if e.get("solver") == "external":
        return "external"
    if not e.get("solved"):
        return "unsolved"
    return "optimal" if e.get("optimal") else "greedy"


def main() -> None:
    corpora = _all_corpora()
    out: list[str] = ["# Corpus statistics", ""]

    # ---- Summary table ---------------------------------------------------------------
    out += [
        "## Summary (per set)",
        "",
        "| corpus | levels | solved | % | opt/greedy/ext | difficulty (solved) med | tiers E/M/H | quality med | fun(like) med |",
        "|---|--:|--:|--:|---|---|---|--:|--:|",
    ]
    grand = {"levels": 0, "solved": 0}
    everything: list[dict] = []
    per_corpus: dict[str, list[dict]] = {}
    for name in corpora:
        es = _enrich(name)
        per_corpus[name] = es
        everything += es
        solved = [e for e in es if e.get("solved")]
        m = [_method(e) for e in es]
        opt, gre, ext = m.count("optimal"), m.count("greedy"), m.count("external")
        tcount = {"easy": 0, "medium": 0, "hard": 0}
        for e in solved:
            tcount[tiers.tier_of(e["difficulty"])] += 1
        dmed = f"{st.median([e['difficulty'] for e in solved]):.2f}" if solved else "—"
        qmed = f"{st.median([e['quality_score'] for e in es]):.2f}"
        lmed = f"{st.median([_ff(e, 'fun_features', 'likeability') for e in es]):.2f}"
        out.append(
            f"| {name} | {len(es)} | {len(solved)} | {100 * len(solved) // max(1, len(es))}% | "
            f"{opt}/{gre}/{ext} | {dmed} | {tcount['easy']}/{tcount['medium']}/{tcount['hard']} | {qmed} | {lmed} |"
        )
        grand["levels"] += len(es)
        grand["solved"] += len(solved)
    out.append(
        f"| **TOTAL** | **{grand['levels']}** | **{grand['solved']}** | "
        f"**{100 * grand['solved'] // grand['levels']}%** | | | | | |"
    )

    # ---- Overall fun/difficulty distribution -----------------------------------------
    sv = [e for e in everything if e.get("solved")]
    out += [
        "",
        "## Overall distributions",
        "",
        "_min / median / mean / max_",
        "",
        f"- **difficulty** (solved, n={len(sv)}): {_s([e['difficulty'] for e in sv])}",
        f"- **quality_score** (all, n={len(everything)}): {_s([e['quality_score'] for e in everything])}",
        f"- **likeability** (all): {_s([_ff(e, 'fun_features', 'likeability') for e in everything])}",
        f"- **boxes** (all): {_s([float(_ff(e, 'fun_features', 'boxes') or e.get('boxes', 0)) for e in everything], '.0f')}",
        f"- **playable_area** (all): {_s([float(_ff(e, 'fun_features', 'playable_area') or 0) for e in everything], '.0f')}",
    ]

    # ---- Per-set breakdown (solved vs geometry-only), compact -------------------------
    out += [
        "",
        "## Per-set breakdown (with solutions vs geometry-only)",
        "",
        "_Each metric is **min / median / mean / max**._",
        "",
    ]
    for name in corpora:
        es = per_corpus[name]
        solved = [e for e in es if e.get("solved")]
        uns = [e for e in es if not e.get("solved")]
        out += [f"### {name} — {len(es)} levels · `{es[0].get('license', '—')}`"]

        if solved:
            t = (sum(1 for e in solved if tiers.tier_of(e["difficulty"]) == k) for k in ("easy", "medium", "hard"))
            conn = sum(1 for e in solved if _ff(e, "structural", "goal_room_connected"))
            out += [
                f"- **with solution: {len(solved)}**  (optimal {sum(1 for e in solved if _method(e) == 'optimal')} · "
                f"greedy {sum(1 for e in solved if _method(e) == 'greedy')} · external {sum(1 for e in solved if _method(e) == 'external')}); "
                f"tiers E/M/H = {'/'.join(map(str, t))}; goal-room-connected {conn}/{len(solved)}",
                f"    - difficulty {_s([e['difficulty'] for e in solved])} · box_change {_s([e['box_change_difficulty'] for e in solved])}",
                f"    - quality {_s([e['quality_score'] for e in solved])} · likeability(fun) {_s([_ff(e, 'fun_features', 'likeability') for e in solved])}",
                f"    - par {_s([e['par'] for e in solved], '.0f')} · moves {_s([e['moves'] for e in solved], '.0f')} · "
                f"boxes {_s([_ff(e, 'fun_features', 'boxes') for e in solved], '.0f')} · area {_s([_ff(e, 'fun_features', 'playable_area') for e in solved], '.0f')}",
                f"    - openness {_s([_ff(e, 'fun_features', 'openness') for e in solved])} · matter {_s([_ff(e, 'structural', 'matter_fraction') for e in solved])} · "
                f"dead-floor {_s([_ff(e, 'structural', 'dead_floor_ratio') for e in solved])} · density {_s([_ff(e, 'structural', 'box_density') for e in solved])} · "
                f"deadlock {_s([_ff(e, 'structural', 'deadlock_proximity') for e in solved])}",
            ]
        if uns:
            out += [
                f"- **without solution (geometry-only): {len(uns)}**  (difficulty=1.0 sentinel; solution-based metrics N/A)",
                f"    - quality {_s([e['quality_score'] for e in uns])} · likeability(fun) {_s([_ff(e, 'fun_features', 'likeability') for e in uns])}",
                f"    - boxes {_s([_ff(e, 'fun_features', 'boxes') for e in uns], '.0f')} · area {_s([_ff(e, 'fun_features', 'playable_area') for e in uns], '.0f')} · "
                f"openness {_s([_ff(e, 'fun_features', 'openness') for e in uns])}",
                f"    - matter {_s([_ff(e, 'structural', 'matter_fraction') for e in uns])} · dead-floor {_s([_ff(e, 'structural', 'dead_floor_ratio') for e in uns])} · "
                f"density {_s([_ff(e, 'structural', 'box_density') for e in uns])} · goal-room-connected "
                f"{sum(1 for e in uns if _ff(e, 'structural', 'goal_room_connected'))}/{len(uns)}",
            ]
        out.append("")

    print("\n".join(out))


if __name__ == "__main__":
    main()
