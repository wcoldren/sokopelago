"""Pure seed-layout helpers — no Archipelago imports, so they're unit-testable.

These compute the region structure and goal requirements from the player's options.
None of this solves Sokoban; it only chunks the level list and counts keys.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def chunk_list(levels: list[int], levels_per_region: int) -> list[list[int]]:
    """Split an explicit level list into worlds of ``levels_per_region`` levels each,
    preserving order. The last world may be smaller."""
    size = max(1, levels_per_region)
    return [levels[i : i + size] for i in range(0, len(levels), size)]


def chunk_levels(level_count: int, levels_per_region: int) -> list[list[int]]:
    """Split the first ``level_count`` Microban numbers (1-based) into worlds of
    ``levels_per_region`` levels each. The last world may be smaller."""
    return chunk_list(list(range(1, level_count + 1)), levels_per_region)


def _bucketize(ordered: list[int], bucket_count: int) -> list[list[int]]:
    """Split a difficulty-ordered level list into ``bucket_count`` near-equal contiguous
    tiers (bucket 0 = easiest). Clamped to at most one bucket per level."""
    n = len(ordered)
    bucket_count = max(1, min(bucket_count, n)) if n else 1
    base, rem = divmod(n, bucket_count)
    buckets: list[list[int]] = []
    i = 0
    for b in range(bucket_count):
        size = base + (1 if b < rem else 0)
        buckets.append(ordered[i : i + size])
        i += size
    return buckets


def _allocate(total: int, sizes: list[int]) -> list[int]:
    """Largest-remainder apportionment of ``total`` picks across buckets of the given
    sizes (proportional to size). ``total <= sum(sizes)`` guarantees no bucket is
    over-allocated, so each result is in ``[0, size]``."""
    grand = sum(sizes)
    if grand <= 0:
        return [0 for _ in sizes]
    quotas = [sz * total for sz in sizes]
    alloc = [q // grand for q in quotas]
    rem = total - sum(alloc)
    # Hand out the leftover picks to the largest fractional remainders (ties by index),
    # so the apportionment is deterministic for a given (total, sizes).
    order = sorted(range(len(sizes)), key=lambda i: (-(quotas[i] % grand), i))
    for i in order[:rem]:
        alloc[i] += 1
    return alloc


def select_bucketed_levels(
    pool: list[int],
    difficulty_by_n: dict[int, float],
    level_count: int,
    bucket_count: int,
    rng: Any,
) -> list[int]:
    """Pick ``level_count`` levels from ``pool`` (the eligible level numbers), varied per
    seed but keeping the difficulty ramp.

    ``pool`` is the candidate set after any ``max_difficulty`` cap — usually the whole
    corpus, but a subset when harder tiers are excluded. Levels are difficulty-ordered,
    split into ``bucket_count`` tiers, shuffled *within* each tier (``rng`` is the
    multiworld's seeded RNG, so different seeds draw different subsets while a given seed
    is reproducible), then a size-proportional share is taken from each tier. The result
    is concatenated easiest-tier-first, so it still ramps easy→hard. Levels missing a
    difficulty score sort as 0 (easiest)."""
    level_count = clamp(level_count, 1, len(pool))
    ordered = sorted(pool, key=lambda n: (difficulty_by_n.get(n, 0.0), n))
    buckets = _bucketize(ordered, bucket_count)
    for bucket in buckets:
        rng.shuffle(bucket)
    alloc = _allocate(level_count, [len(b) for b in buckets])
    selected: list[int] = []
    for bucket, take in zip(buckets, alloc, strict=True):
        selected.extend(bucket[:take])
    return selected


def solve_count_keys_needed(world_sizes: list[int], target: int) -> int:
    """Minimum number of (any) world keys that guarantees at least ``target`` levels
    are reachable. World 1 (index 0) is free; the rest need keys. Worst-case: assume
    the player opens the *smallest* keyed worlds first, so the bound is sound no matter
    which keys fill placement makes reachable first."""
    if not world_sizes:
        return 0
    free = world_sizes[0]
    if target <= free:
        return 0
    keyed_sorted = sorted(world_sizes[1:])
    reachable = free
    for k, size in enumerate(keyed_sorted, start=1):
        reachable += size
        if reachable >= target:
            return k
    return len(keyed_sorted)  # target clamped to level_count, so this always suffices


def floor_schedule(region_count: int, group: int, cap: int) -> list[int]:
    """Per-world key-count floor for the chained-access layout (returned 1-based: index
    ``i-1`` is the floor for World ``i``).

    World 1 is free (floor 0). Each body world ``i`` in ``2..N-1`` requires its own key AND
    at least ``floor`` *other* keys already held, where the floor steps up every ``group``
    worlds: ``min((i-2)//group, cap)``. The caller passes ``cap = region_count-2`` so a body
    floor never exceeds the count of strictly-earlier keyed worlds — the fillability
    invariant ``floor_i <= i-2`` (which holds because ``(i-2)//group <= i-2`` for
    ``group >= 1``), guaranteeing a valid, non-decreasing sphere order. The boss world ``N``
    is the all-keys special case (enforced by the access rule, not this schedule) and is
    reported here as ``region_count-1`` for slot_data / diagnostics.

    Returns a list of length ``region_count`` (``[]`` when ``region_count <= 0``)."""
    if region_count <= 0:
        return []
    group = max(1, group)
    cap = max(0, cap)
    floors = [0]  # World 1 is free
    floors += [min((i - 2) // group, cap) for i in range(2, region_count)]  # body worlds 2..N-1
    if region_count >= 2:
        floors.append(region_count - 1)  # boss world N: all keys
    return floors


# Solo fill (fill_restrictive) reliably places the count-floor key chain only while it stays
# shallow; past a handful of keys of depth its swap search starts failing on tight seeds even
# though a valid placement always exists. effective_floor_schedule caps the *effective* chain
# depth by raising the group as the world count grows. 4 keeps every option combination at a 0%
# fill-failure rate in stress testing (thousands of solo seeds) while leaving the default
# layout's steepness untouched (ceil(6/4) == 2 == the default group).
DEFAULT_CHAIN_MAX_DEPTH = 4


def effective_floor_schedule(world_sizes: list[int], chain_group: int, max_depth: int, chained: bool) -> list[int]:
    """The per-world key-count floors actually enforced for a seed (1-based; index ``i-1`` is
    World ``i``), given the worlds' sizes.

    Layers fill-robustness guards on top of ``floor_schedule``; both only ever *raise* the group
    (gentler chain), so the fillability invariant always holds:
      - Non-beat_final_region goals (``chained=False``) and single-world seeds → flat (all 0).
      - **Zero-slack** layouts — where the keys exactly fill the non-boss worlds (e.g. one level
        per region) — flatten the body floors and keep only the all-keys boss gate, since a tight
        nested count-floor chain is an unreliable fill.
      - Otherwise bound the effective steepness: narrow worlds (smallest non-boss world < 3) get
        at least group 2, and the staircase rises at most ~``max_depth`` times overall (group is
        raised to ``ceil(region_count / max_depth)``), so the deepest body floor stays shallow no
        matter how many worlds there are.
    """
    n = len(world_sizes)
    if not chained or n <= 1:
        return [0] * n
    body_sizes = world_sizes[:-1]  # worlds 1..N-1 (exclude the boss)
    spare = sum(body_sizes) - (n - 1)  # non-boss locations left after the keys
    if spare < 1:
        return [0] * (n - 1) + [n - 1]  # flat body, boss informational
    group = chain_group if min(body_sizes) >= 3 else max(chain_group, 2)
    group = max(group, -(-n // max(1, max_depth)))  # ceil(n / max_depth)
    return floor_schedule(n, group, n - 2)


def boss_world_index(worlds: list[list[int]], boss_level: int) -> int:
    """1-based index of the world containing ``boss_level``. Falls back to the last
    world if the level isn't found (shouldn't happen after clamping)."""
    for i, world in enumerate(worlds, start=1):
        if boss_level in world:
            return i
    return len(worlds)


# Escape-valve items are carved out of the filler budget (never added on top), so the
# item pool stays exactly ``level_count``. When the budget can't hold every requested
# valve, drop them in this priority order — a skip token is the load-bearing one.
ESCAPE_VALVE_PRIORITY = ("skip", "hint", "undo", "trap")


def escape_valve_counts(budget: int, requested: dict[str, int]) -> dict[str, int]:
    """Clamp requested escape-valve counts so their sum fits ``budget``.

    Fills greedily in ``ESCAPE_VALVE_PRIORITY`` order, so when room is tight the skip
    token survives first and traps are sacrificed first. Returns a dict with every
    priority key present (0 when nothing fits)."""
    remaining = max(0, budget)
    counts = dict.fromkeys(ESCAPE_VALVE_PRIORITY, 0)
    for key in ESCAPE_VALVE_PRIORITY:
        want = max(0, requested.get(key, 0))
        take = min(want, remaining)
        counts[key] = take
        remaining -= take
    return counts


def assign_levels_by_difficulty(
    levels: list[int],
    difficulty: dict[int, float],
    levels_per_region: int,
) -> list[list[int]]:
    """Distribute levels into worlds balanced by measured difficulty.

    Produces the same world count and per-world sizes as ``chunk_levels`` (so key
    counting and goal logic are unchanged), but deals difficulty-sorted levels
    round-robin across worlds so no single key-gated world is a brutal cluster, then
    orders each world easiest-first. Levels missing a difficulty score sort as 0."""
    sizes = [len(world) for world in chunk_list(levels, levels_per_region)]
    worlds: list[list[int]] = [[] for _ in sizes]
    ordered = sorted(levels, key=lambda n: (difficulty.get(n, 0.0), n))
    wi = 0
    for lvl in ordered:
        while len(worlds[wi]) >= sizes[wi]:
            wi = (wi + 1) % len(sizes)
        worlds[wi].append(lvl)
        wi = (wi + 1) % len(sizes)
    for world in worlds:
        world.sort(key=lambda n: (difficulty.get(n, 0.0), n))
    return worlds


def gentle_first_world(
    levels: list[int],
    difficulty: dict[int, float],
    easy_max: float,
    levels_per_region: int,
    reassign: Callable[[list[int]], list[list[int]]],
) -> list[list[int]]:
    """Lay out ``levels`` so World 1 holds only easy-tier puzzles (difficulty < ``easy_max``),
    for a gentle start, then lay out the rest with ``reassign``.

    The easiest easy-tier levels (up to ``levels_per_region``) become World 1; every other
    level — leftover easy ones plus all harder ones — is laid out into Worlds 2..N by
    ``reassign`` (the normal difficulty-ordered or native chunking). No-op (returns
    ``reassign(levels)``) when the seed has no easy levels (can't form a gentle world) or no
    harder levels (every world is already easy)."""
    easy = [n for n in levels if difficulty.get(n, 1.0) < easy_max]
    harder = [n for n in levels if difficulty.get(n, 1.0) >= easy_max]
    if not easy or not harder:
        return reassign(levels)
    first = sorted(easy, key=lambda n: (difficulty.get(n, 1.0), n))[:levels_per_region]
    first_set = set(first)
    rest = [n for n in levels if n not in first_set]
    return [first, *reassign(rest)]
