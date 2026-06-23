#!/usr/bin/env python3
"""Simulate a Sokopelago multiworld seed from a combined pool of curated corpora — *without*
generating anything through Archipelago or touching the shipped game.

It reuses the apworld's REAL selection/layout logic (the exact functions
``apworld/sokopelago/__init__.py:generate_early`` calls — ``corpus.load_corpus_data`` +
``layout`` + ``tiers``), so the output matches what ``Generate.py`` would produce if the new
corpora were a selectable merged corpus. The new sets are committed *dataset-only* (not in
``CORPUS_NAMES``); this previews "what a seed would look like" with them.

Default config = "10 worlds × 10 puzzles" (level_count 100, levels_per_region 10) over the new
curated sets' *solved* levels (real difficulty, playable with hints).

Run:  python tools/preview_seed.py
      python tools/preview_seed.py --max-difficulty easy_medium --seed 7
      python tools/preview_seed.py --corpora microban2,microban3 --include-unsolved
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics as st
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "apworld", "sokopelago"))  # pure modules (like conftest)

import layout
import tiers

DATA_DIR = os.path.join(_HERE, "..", "apworld", "sokopelago", "data")
NEW_SETS = ["microban2", "microban3", *[f"sasquatch{i}" for i in range(1, 10)], "xsokoban90"]

# Item name strings (reproduced from Items.py, which can't import without BaseClasses).
FILLER_NAME = "Sokoban Token"
VALVE_NAMES = {"skip": "Skip Token", "undo": "Undo Charge", "hint": "Hint Token"}


class Lvl:
    """One level in the combined virtual corpus (global id -> source metadata)."""

    __slots__ = ("boxes", "corpus", "difficulty", "fun", "gid", "n", "name", "solved")

    def __init__(self, gid, corpus, e):
        self.gid = gid
        self.corpus = corpus
        self.n = e["n"]
        self.name = e.get("name", str(e["n"]))
        self.difficulty = float(e.get("difficulty", 1.0))
        self.solved = bool(e.get("solved"))
        self.boxes = (e.get("fun_features") or {}).get("boxes", e.get("boxes"))
        self.fun = (e.get("fun_features") or {}).get("likeability")

    def label(self):
        return f"{self.corpus}:{self.n}"


def build_pool(corpora, include_unsolved):
    """Combined pool as a list[Lvl] with global ids 1..N (the merged-corpus indexing)."""
    pool, gid = [], 0
    for name in corpora:
        for e in json.loads(open(os.path.join(DATA_DIR, f"{name}.json")).read()):
            if not include_unsolved and not e.get("solved"):
                continue
            gid += 1
            pool.append(Lvl(gid, name, e))
    return pool


def _s(xs, fmt=".2f"):
    xs = [x for x in xs if x is not None]
    return f"{min(xs):{fmt}}/{st.median(xs):{fmt}}/{max(xs):{fmt}}" if xs else "—"


def simulate(args):
    pool = build_pool(args.corpora, args.include_unsolved)
    by_gid = {lv.gid: lv for lv in pool}
    diff = {lv.gid: lv.difficulty for lv in pool}

    # --- generate_early, faithfully (apworld/sokopelago/__init__.py:88-156) ---------------
    ceiling = tiers.MAX_DIFFICULTY_CEILING[args.max_difficulty]
    allowed = [g for g in range(1, len(pool) + 1) if tiers.within_cap(diff.get(g, 1.0), ceiling)]
    if not allowed:
        raise SystemExit(f"max_difficulty='{args.max_difficulty}' leaves no levels in the pool.")
    level_count = min(layout.clamp(args.levels, 5, len(pool)), len(allowed))
    levels_per_region = layout.clamp(args.per_region, 1, level_count)
    rng = random.Random(args.seed)
    if args.selection == "shuffled_buckets":
        levels = layout.select_bucketed_levels(allowed, diff, level_count, args.buckets, rng)
    else:
        levels = allowed[:level_count]

    def reassign(lvls):
        return layout.assign_levels_by_difficulty(lvls, diff, levels_per_region)  # difficulty_ordering on

    if args.gentle:  # shipped default: World 1 is easy-tier only (=> a small World 1 + a partial tail)
        worlds = layout.gentle_first_world(levels, diff, tiers.EASY_MAX, levels_per_region, reassign)
    else:  # clean N×per_region split (difficulty-balanced worlds)
        worlds = reassign(levels)
    if len(worlds[0]) > 1:
        rng.shuffle(worlds[0])
    region_count = len(worlds)

    # --- item / location pool (create_items: keys = region_count-1; budget = locs - keys) --
    sizes = [len(w) for w in worlds]
    floors = layout.effective_floor_schedule(
        sizes, layout.clamp(args.chain_group, 1, max(1, region_count)), layout.DEFAULT_CHAIN_MAX_DEPTH, chained=True
    )
    keys = region_count - 1
    total_locations = level_count  # par/eff checks off
    budget = total_locations - keys
    valves = layout.escape_valve_counts(budget, {"skip": args.skip, "hint": args.hint, "undo": args.undo, "trap": 0})
    filler = budget - sum(valves.values())

    # ---------------------------------- render --------------------------------------------
    out = []
    out.append("=" * 78)
    out.append("SOKOPELAGO SEED PREVIEW (simulation — reuses the real apworld layout logic)")
    out.append("=" * 78)
    out.append(f"pool         : combined new corpora {args.corpora}")
    out.append(f"               {len(pool)} levels ({'solved+unsolved' if args.include_unsolved else 'solved only'})")
    out.append(
        f"config       : level_count={level_count}  levels_per_region={levels_per_region}  -> {region_count} worlds"
    )
    out.append(
        f"               max_difficulty={args.max_difficulty}  selection={args.selection}  "
        f"seed={args.seed}  goal=beat_final_region"
    )
    out.append(
        f"               difficulty_ordering=on  gentle_first_world={'on' if args.gentle else 'off'}"
        + ("" if args.gentle else "  (shipped default is ON -> a small easy World 1 + 10 => 11 worlds)")
    )
    poolt = {k: sum(1 for lv in pool if tiers.tier_of(lv.difficulty) == k) for k in ("easy", "medium", "hard")}
    out.append(
        f"pool spread  : easy {poolt['easy']} / medium {poolt['medium']} / hard {poolt['hard']}  "
        f"| eligible under cap: {len(allowed)}"
    )
    if level_count < args.levels:
        out.append(
            f"  NOTE: requested {args.levels} but only {level_count} eligible under the cap -> {region_count} worlds."
        )
    out.append("")

    # worlds
    sel = [by_gid[g] for g in levels]
    st_tier = {k: sum(1 for lv in sel if tiers.tier_of(lv.difficulty) == k) for k in ("easy", "medium", "hard")}
    out.append(
        f"SELECTED {len(sel)} PUZZLES — tiers easy {st_tier['easy']} / medium {st_tier['medium']} "
        f"/ hard {st_tier['hard']}; sources: "
        + ", ".join(
            f"{c}×{sum(1 for lv in sel if lv.corpus == c)}" for c in args.corpora if any(lv.corpus == c for lv in sel)
        )
    )
    out.append("")
    for i, world in enumerate(worlds, start=1):
        lvs = [by_gid[g] for g in world]
        ds = [lv.difficulty for lv in lvs]
        gate = (
            "free (sphere 1)"
            if i == 1
            else "boss — needs ALL keys"
            if i == region_count
            else f"needs World {i} Key + {floors[i - 1]} earlier key(s)"
        )
        tmix = "/".join(
            str(sum(1 for lv in lvs if tiers.tier_of(lv.difficulty) == k)) for k in ("easy", "medium", "hard")
        )
        out.append(f"World {i:>2}  ({len(lvs)} puzzles)  diff {_s(ds)}  E/M/H {tmix}  —  {gate}")
        for lv in lvs:
            flag = "" if lv.solved else "  [UNSOLVED: no hint/par]"
            funv = f"{lv.fun:.2f}" if lv.fun is not None else "—"
            out.append(
                f"        {lv.label():>14}  {lv.name[:22]:<22}  "
                f"diff {lv.difficulty:.2f} ({tiers.tier_of(lv.difficulty)[:3]})  "
                f"boxes {lv.boxes!s:>3}  fun {funv}{flag}"
            )
        out.append("")

    # item / location pool
    out.append("-" * 78)
    out.append("AP ITEM POOL  (one item per location; pool size == location count)")
    out.append(f"  locations : {total_locations}  ('Solve <name>' — one per puzzle; par/eff checks off)")
    out.append(f"  progression: {keys} World Keys (World 2 Key … World {region_count} Key)")
    out.append(
        f"  escape valves: {valves['skip']}× Skip Token · {valves['hint']}× Hint Token · {valves['undo']}× Undo Charge"
    )
    out.append(f"  filler    : {filler}× {FILLER_NAME}")
    out.append(
        f"  CHECK     : {keys} keys + {sum(valves.values())} valves + {filler} filler "
        f"= {keys + sum(valves.values()) + filler}  (== {total_locations} locations ✓)"
    )
    out.append("")
    out.append("REGION MAP / GATING")
    out.append("  Menu")
    for i in range(1, region_count + 1):
        if i == 1:
            g = "[free]"
        elif i == region_count:
            g = f"[BOSS: hold all {keys} keys]"
        else:
            g = f"[World {i} Key + {floors[i - 1]}-key floor]"
        out.append(f"   -> World {i} ({sizes[i - 1]} puzzles) {g}")
    out.append(f"  GOAL: beat_final_region — hold all {keys} World Keys to reach World {region_count}.")
    print("\n".join(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpora", default=",".join(NEW_SETS), help="comma list of corpora for the pool")
    ap.add_argument("--levels", type=int, default=100)
    ap.add_argument("--per-region", type=int, default=10)
    ap.add_argument("--max-difficulty", default="any", choices=["any", "easy", "easy_medium"])
    ap.add_argument("--selection", default="shuffled_buckets", choices=["shuffled_buckets", "native"])
    ap.add_argument("--buckets", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--chain-group", type=int, default=2)
    ap.add_argument("--skip", type=int, default=5)
    ap.add_argument("--hint", type=int, default=10)
    ap.add_argument("--undo", type=int, default=10)
    ap.add_argument(
        "--gentle",
        action="store_true",
        help="gentle_first_world (shipped default ON): easy-only World 1 -> 11 worlds. "
        "Off (this tool's default) gives a clean 10x10 of difficulty-balanced worlds.",
    )
    ap.add_argument(
        "--include-unsolved",
        action="store_true",
        help="include unsolved (difficulty=1.0, hint-less) levels — what a real "
        "max_difficulty=any run on the raw corpora would do",
    )
    args = ap.parse_args()
    args.corpora = [c for c in args.corpora.split(",") if c]
    simulate(args)


if __name__ == "__main__":
    main()
