"""Sokopelago — a Sokoban world for Archipelago.

Region-key access logic: levels are grouped into worlds; each world after the first is opened by a
"World n Key" shuffled into the multiworld. A location is reachable iff its world's key is held,
plus (for the ``beat_final_region`` goal) count-floor chaining — a body world also needs a floor of
earlier keys, and the final ("boss") world needs ALL keys, so seeds play in real sphere order (see
``create_regions`` / ``set_rules`` and ``docs/DESIGN-boss-zone.md``). The client mirrors this gate
from ``slot_data`` and enforces the precise "levels solved" win.

The generator never solves Sokoban: it only reads the bundled level manifest
(``corpus.py`` / ``data/<corpus>.json``) for counts, names, par, difficulty, and pull gates.
"""

from __future__ import annotations

from typing import Any

from BaseClasses import LocationProgressType, Region
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from .corpus import CorpusData, load_corpus_data
from .Items import (
    FILLER_NAME,
    PULL_NAME,
    TRAP_ITEM_NAMES,
    VALVE_ITEM_NAMES,
    SokopelagoItem,
    item_name_to_id,
    item_table,
    world_key_name,
)
from .layout import (
    DEFAULT_CHAIN_MAX_DEPTH,
    assign_levels_by_difficulty,
    boss_world_index,
    chunk_list,
    clamp,
    effective_floor_schedule,
    escape_valve_counts,
    gentle_first_world,
    select_bucketed_levels,
    solve_count_keys_needed,
)
from .Locations import (
    SokopelagoLocation,
    eff_location_name,
    eff_location_table,
    location_name_to_id,
    location_table,
    par_location_name,
    par_location_table,
    solve_location_name,
)
from .Options import SokopelagoOptions
from .tiers import EASY_MAX, MAX_DIFFICULTY_CEILING, within_cap


class SokopelagoWeb(WebWorld):
    theme = "dirt"


class SokopelagoWorld(World):
    """Solve Sokoban levels to send items to other players; receive region keys that
    open new worlds of puzzles."""

    game = "Sokopelago"
    options_dataclass = SokopelagoOptions
    options: SokopelagoOptions
    web = SokopelagoWeb()
    topology_present = True

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    # Set in generate_early.
    corpus_data: CorpusData
    worlds: list[list[int]]
    region_count: int
    level_count: int
    levels_per_region: int
    chain_group: int  # count-floor chaining steepness (beat_final_region only)
    goal_solve_count: int
    boss_level: int
    pull_logic: bool
    pull_levels: set[int]  # seed levels hard-gated behind the Pull ability (pull-logic only)

    def generate_early(self) -> None:
        self.corpus_data = load_corpus_data(self.options.corpus.current_key)
        diff = self.corpus_data.difficulty_by_n
        # max_difficulty caps the candidate pool *before* selection, so Level Count draws
        # from the eligible tiers (clamped down to them). Levels lacking a difficulty score
        # are treated as hardest, so a cap excludes them; with no scores at all the cap is
        # a no-op (the whole corpus is eligible).
        ceiling = MAX_DIFFICULTY_CEILING[self.options.max_difficulty.current_key]
        if diff:
            allowed = [n for n in range(1, self.corpus_data.count + 1) if within_cap(diff.get(n, 1.0), ceiling)]
        else:
            allowed = list(range(1, self.corpus_data.count + 1))
        if not allowed:
            raise OptionError(
                f"Sokopelago: max_difficulty='{self.options.max_difficulty.current_key}' leaves no "
                f"levels in corpus '{self.corpus_data.name}'."
            )
        self.level_count = min(clamp(self.options.level_count.value, 5, self.corpus_data.count), len(allowed))
        self.levels_per_region = clamp(self.options.levels_per_region.value, 1, self.level_count)
        if self.options.level_selection == "shuffled_buckets":
            # Vary which puzzles a seed draws (per the multiworld's seeded RNG) while
            # keeping the difficulty ramp; native selection is the first N of the pool.
            levels = select_bucketed_levels(
                allowed,
                diff,
                self.level_count,
                self.options.difficulty_buckets.value,
                self.multiworld.random,
            )
        else:
            levels = allowed[: self.level_count]

        def reassign(lvls: list[int]) -> list[list[int]]:
            if self.options.difficulty_ordering.value and diff:
                return assign_levels_by_difficulty(lvls, diff, self.levels_per_region)
            return chunk_list(lvls, self.levels_per_region)

        if self.options.gentle_first_world.value and diff:
            # Keep World 1 easy-tier only for a gentle start; lay out the rest normally.
            self.worlds = gentle_first_world(levels, diff, EASY_MAX, self.levels_per_region, reassign)
        else:
            self.worlds = reassign(levels)
        # World 1 is sphere 1 (no key gate), and every layout path orders it easiest-first,
        # so its slot-0 level is the globally-easiest drawn level — identical across seeds
        # with the same options. Shuffle World 1's internal order so the opening puzzle
        # varies per seed. Downstream logic reads World 1 by membership/size, not order
        # (key counting, boss_world_index, pull_levels, goal/solve-count, slot_data), so
        # this is safe; the client renders in slot_data order, so the picker follows.
        if len(self.worlds[0]) > 1:
            self.multiworld.random.shuffle(self.worlds[0])
        self.region_count = len(self.worlds)
        # Count-floor chaining steepness; clamped to the world count (a value >= the world
        # count flattens the body floors back to the classic single-key star).
        self.chain_group = clamp(self.options.chain_group.value, 1, max(1, self.region_count))
        self.goal_solve_count = clamp(self.options.goal_solve_count.value, 1, self.level_count)
        # Resolve the boss to an actually-selected level: 0 -> the highest-numbered level
        # in the seed ("the last level"); otherwise the requested number if it was drawn,
        # else the nearest drawn level (ties favour the lower number). Under shuffled_buckets
        # the requested number may not be in the seed, so "nearest" keeps the goal valid.
        raw_boss = self.options.goal_boss_level.value
        if raw_boss == 0:
            self.boss_level = max(levels)
        elif raw_boss in levels:
            self.boss_level = raw_boss
        else:
            self.boss_level = min(levels, key=lambda n: (abs(n - raw_boss), n))
        # Pull Logic: hard-gate the seed's pull-required levels behind the Pull item.
        self.pull_logic = bool(self.options.pull_logic.value)
        self.pull_levels = {n for n in levels if n in self.corpus_data.requires_pull} if self.pull_logic else set()

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        par_checks = bool(self.options.par_checks.value)
        eff_checks = par_checks and bool(self.options.efficiency_checks.value)

        # 0.7 "accurate logic" (beat_final_region only): the final world is gated on ALL
        # keys so it is always the deepest sphere, and body worlds chain behind a count-floor
        # of earlier keys. solve_count / boss_level keep the 0.6 single-key-per-world layout
        # (their key counting assumes single-key access), so they stay experimental.
        chained = self.options.goal == "beat_final_region"
        all_keys = tuple(world_key_name(n) for n in range(2, self.region_count + 1))
        floors = self._effective_floors()

        for i, level_ns in enumerate(self.worlds, start=1):
            region = Region(f"World {i}", self.player, self.multiworld)
            for n in level_ns:
                loc_name = solve_location_name(n)
                loc = SokopelagoLocation(self.player, loc_name, location_table[loc_name], region)
                self._apply_pull_gate(loc, n)
                region.locations.append(loc)
                if par_checks:
                    # The par/efficiency locations share the region's key gate, but are
                    # EXCLUDED so only filler lands there — a hard push-count requirement
                    # (which escape valves can't bypass) can never strand a progression
                    # item. Par = exactly optimal (perfect); efficiency = within margin.
                    # (EXCLUDED already rejects the Pull item, so the item-floor is moot here.)
                    self._add_excluded_check(region, par_location_name(n), par_location_table, n)
                    if eff_checks:
                        self._add_excluded_check(region, eff_location_name(n), eff_location_table, n)
            self.multiworld.regions.append(region)

            if i == 1:
                menu.connect(region, f"Menu -> World {i}")
            elif chained and i == self.region_count:
                # Boss world: gated on ALL keys, so it is always the deepest sphere — closing
                # the find-the-final-key-first hole (docs/DESIGN-boss-zone.md). No key can fill
                # here: a key placed in the boss world would need itself to be reachable.
                menu.connect(
                    region,
                    f"Menu -> World {i}",
                    rule=lambda state, keys=all_keys: state.has_all(keys, self.player),
                )
            else:
                # Body world (and the boss world when chaining is off): own key, plus a
                # count-floor of any earlier keys when chaining is active. floor_i counts all
                # held keys incl. this world's own, so min keys to enter = max(1, floor_i). All
                # loop-varying values are bound by default arg to avoid late-binding capture.
                key = world_key_name(i)
                floor_i = floors[i - 1] if chained else 0
                if floor_i > 0:
                    menu.connect(
                        region,
                        f"Menu -> World {i}",
                        rule=lambda state, k=key, keys=all_keys, f=floor_i: (
                            state.has(k, self.player) and state.has_from_list(keys, self.player, f)
                        ),
                    )
                else:
                    menu.connect(
                        region,
                        f"Menu -> World {i}",
                        rule=lambda state, k=key: state.has(k, self.player),
                    )

    def _effective_floors(self) -> list[int]:
        """Per-world key-count floors actually enforced (1-based; index ``i-1`` = World ``i``).
        Delegates to the pure ``effective_floor_schedule`` (flatten on zero-slack, bound depth);
        chaining + the all-keys boss gate are beat_final_region-only."""
        chained = self.options.goal == "beat_final_region"
        sizes = [len(world) for world in self.worlds]
        return effective_floor_schedule(sizes, self.chain_group, DEFAULT_CHAIN_MAX_DEPTH, chained)

    def _apply_pull_gate(self, loc: SokopelagoLocation, n: int) -> None:
        """Gate a pull-required level's location behind the Pull item (expert logic)."""
        if n in self.pull_levels:
            loc.access_rule = lambda state, p=self.player: state.has(PULL_NAME, p)

    def _add_excluded_check(self, region: Region, name: str, table: dict[str, int], n: int) -> None:
        """Attach a filler-only (EXCLUDED) skill check (par/efficiency) for level ``n``,
        sharing the region key gate and the level's pull gate."""
        loc = SokopelagoLocation(self.player, name, table[name], region)
        loc.progress_type = LocationProgressType.EXCLUDED
        self._apply_pull_gate(loc, n)
        region.locations.append(loc)

    def create_items(self) -> None:
        keys: list[SokopelagoItem] = [self.create_item(world_key_name(n)) for n in range(2, self.region_count + 1)]
        # Pull Logic adds one Pull ability (progression) that gates the pull-required
        # levels. Like the keys it's a fixed progression item; it's carved from the budget
        # so the pool size stays exactly the location count.
        abilities: list[SokopelagoItem] = [self.create_item(PULL_NAME)] if self.pull_levels else []
        # One item per location. Par Checks adds a second (EXCLUDED) location per level and
        # Efficiency Checks a third, so the pool must grow to match; the extra slots are
        # plain filler.
        par_checks = bool(self.options.par_checks.value)
        eff_checks = par_checks and bool(self.options.efficiency_checks.value)
        per_level = 1 + (1 if par_checks else 0) + (1 if eff_checks else 0)
        total_locations = self.level_count * per_level
        budget = total_locations - len(keys) - len(abilities)  # non-key/ability items the pool can hold
        extras = self._escape_valve_items(budget)
        filler = [self.create_filler() for _ in range(budget - len(extras))]
        self.multiworld.itempool += keys + abilities + extras + filler

    def _escape_valve_items(self, budget: int) -> list[SokopelagoItem]:
        """Escape-valve + trap items, carved out of the filler budget (never on top),
        so the pool size stays exactly the location count. Counts are clamped to fit."""
        # Trap density tracks the level count (not the enlarged budget) so enabling Par
        # Checks doesn't silently double the number of traps.
        trap_count = min(budget, (self.level_count * self.options.trap_percentage.value) // 100)
        requested = {
            "skip": self.options.skip_tokens.value,
            "hint": self.options.hint_tokens.value,
            "undo": self.options.undo_charges.value,
            "trap": trap_count,
        }
        counts = escape_valve_counts(budget, requested)
        items: list[SokopelagoItem] = []
        for key in ("skip", "hint", "undo"):
            items += [self.create_item(VALVE_ITEM_NAMES[key]) for _ in range(counts[key])]
        for i in range(counts["trap"]):  # spread the trap budget across the variants
            items.append(self.create_item(TRAP_ITEM_NAMES[i % len(TRAP_ITEM_NAMES)]))
        return items

    def _completion(self, base: Any) -> Any:
        """Wrap a key-based completion rule, ANDing in Pull when pull logic gates levels
        (winning means solving the pull-gated levels, so Pull is genuinely required)."""
        if self.pull_levels:
            player = self.player
            return lambda state: base(state) and state.has(PULL_NAME, player)
        return base

    def set_rules(self) -> None:
        player = self.player
        goal = self.options.goal
        all_keys = [world_key_name(n) for n in range(2, self.region_count + 1)]
        cc = self.multiworld.completion_condition

        if goal == "solve_count":
            k = solve_count_keys_needed([len(w) for w in self.worlds], self.goal_solve_count)
            if k == 0:
                cc[player] = self._completion(lambda s: True)
            else:
                cc[player] = self._completion(lambda s: s.has_from_list(all_keys, player, k))
        elif goal == "boss_level":
            bw = boss_world_index(self.worlds, self.boss_level)
            boss_key = world_key_name(bw)
            cc[player] = self._completion((lambda s: True) if bw == 1 else (lambda s, key=boss_key: s.has(key, player)))
        else:  # beat_final_region
            # Winning requires the boss world, which is gated on ALL keys (see create_regions),
            # so completion holds only once every key is collected — no early win from drawing
            # the final key first. has_all over the full key set is false until all are held.
            single = self.region_count <= 1
            cc[player] = self._completion(
                (lambda s: True) if single else (lambda s, keys=tuple(all_keys): s.has_all(keys, player))
            )

    def create_item(self, name: str) -> SokopelagoItem:
        data = item_table[name]
        return SokopelagoItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return FILLER_NAME

    def fill_slot_data(self) -> dict[str, Any]:
        seed_levels = [n for world in self.worlds for n in world]
        par_by_n = self.corpus_data.par_by_n
        difficulty_by_n = self.corpus_data.difficulty_by_n
        # Ship the RESOLVED per-world key-count floors (the same ones create_regions enforces,
        # via _effective_floors) so the client gate can never drift from a re-derived formula.
        # Chaining + the all-keys boss gate are beat_final_region-only, so other goals report
        # flat floors and no boss-all-keys flag.
        chained = self.options.goal == "beat_final_region"
        floors = self._effective_floors()
        chain_floors = {str(i): floors[i - 1] for i in range(1, self.region_count + 1)}
        return {
            "corpus": self.corpus_data.name,
            "level_count": self.level_count,
            "levels_per_region": self.levels_per_region,
            "levels": seed_levels,
            "region_map": {str(i): world for i, world in enumerate(self.worlds, start=1)},
            "goal": self.options.goal.current_key,
            "goal_solve_count": self.goal_solve_count,
            "goal_boss_level": self.boss_level,
            "final_world": self.region_count,
            # 0.7 accurate logic: per-world key-count floor (world index as string key) and the
            # all-keys boss flag. A world unlocks when its own key is held AND total keys held
            # >= its floor; the final_world unlocks only on all keys when boss_all_keys is set.
            "chain_floors": chain_floors,
            "boss_all_keys": chained and self.region_count > 1,
            # When on, the client sends the parallel par-location check for any level
            # solved within its push-par (the "perfect" tier — exactly optimal).
            "par_checks": bool(self.options.par_checks.value),
            # Efficiency tier (only meaningful with par_checks): the client also sends an
            # efficiency-location check when a solve is within efficiency_margin percent
            # over optimal, i.e. pushes <= floor(par * (1 + efficiency_margin/100)).
            "efficiency_checks": bool(self.options.par_checks.value) and bool(self.options.efficiency_checks.value),
            "efficiency_margin": self.options.efficiency_margin.value,
            # Pull Logic (Phase 5): when on, the client requires the Pull item before
            # the listed levels can be played; requires_pull maps those level numbers.
            "pull_logic": self.pull_logic,
            "requires_pull": {str(n): True for n in sorted(self.pull_levels)},
            # Per-level par + normalized difficulty for the client's UI / hints. Full
            # solution strings are NOT shipped here (bloat) — the client reads those
            # from the bundled manifest it serves.
            "par": {str(n): par_by_n[n] for n in seed_levels if n in par_by_n},
            "difficulty": {str(n): difficulty_by_n[n] for n in seed_levels if n in difficulty_by_n},
            "seed_name": self.multiworld.seed_name,
            "player_name": self.player_name,
            "player_id": self.player,
        }
