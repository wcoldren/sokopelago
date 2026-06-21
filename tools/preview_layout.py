#!/usr/bin/env python3
"""Preview a seed's world layout + count-floor key chain for a given set of options.

A tuning aid for the 0.7 "accurate logic" knobs (level_count / levels_per_region /
chain_group): it prints, per world, the level range, size, the key-count floor actually
enforced, and the free/boss markers — so you can eyeball how steep the chain feels before
generating. Pure: it never solves Sokoban and never touches Archipelago. It reuses the same
``layout.py`` helpers the apworld uses (``chunk_levels`` + ``effective_floor_schedule``), so
the floors shown are exactly the ones the generator and client gate on.

Note: this previews the *native* contiguous chunking. With difficulty ordering / gentle first
world the per-world *sizes* match, but which levels land where differs; the floors (driven by
sizes) are identical.

    python tools/preview_layout.py --level-count 30 --levels-per-region 5 --chain-group 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Import the pure layout helpers directly (no Archipelago env): adding the package dir to the
# path imports layout.py without triggering the package __init__ (which needs BaseClasses).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apworld" / "sokopelago"))

from layout import (
    DEFAULT_CHAIN_MAX_DEPTH,
    chunk_levels,
    effective_floor_schedule,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Preview the world layout + count-floor key chain.")
    ap.add_argument("--level-count", type=int, default=30)
    ap.add_argument("--levels-per-region", type=int, default=5)
    ap.add_argument("--chain-group", type=int, default=2, help="lower = steeper (boss always all-keys)")
    ap.add_argument(
        "--goal",
        default="beat_final_region",
        help="non-beat_final_region goals use the flat single-key layout",
    )
    ap.add_argument("--max-depth", type=int, default=DEFAULT_CHAIN_MAX_DEPTH, help="effective chain-depth cap")
    args = ap.parse_args()

    worlds = chunk_levels(args.level_count, args.levels_per_region)
    sizes = [len(w) for w in worlds]
    chained = args.goal == "beat_final_region"
    floors = effective_floor_schedule(sizes, args.chain_group, args.max_depth, chained)
    n = len(worlds)

    print(
        f"level_count={args.level_count} levels_per_region={args.levels_per_region} "
        f"chain_group={args.chain_group} goal={args.goal} -> {n} world(s)"
    )
    for i, world in enumerate(worlds, start=1):
        floor = floors[i - 1]
        if i == 1:
            tag = "(free)"
        elif chained and i == n:
            tag = "(BOSS: all keys)"
        else:
            # min keys to enter = max(1, floor), since the world's own key counts toward the floor
            tag = f"needs own key + total keys >= {floor}  (min {max(1, floor)} keys)"
        rng = f"L{world[0]}-{world[-1]}" if world else "—"
        print(f"  W{i:<3d} {rng:<12s} size {len(world):<3d} floor {floor:<3d} {tag}")


if __name__ == "__main__":
    main()
