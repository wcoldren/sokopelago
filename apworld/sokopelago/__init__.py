"""Sokopelago — a Sokoban world for Archipelago.

Phase 1: region-key access logic. Levels are grouped into worlds; each world after
the first is opened by a "World n Key" shuffled into the multiworld. A location is
reachable iff its world's key is held — standard region-access logic. The goal is an
item-reachability condition (see ``set_rules``); the client enforces the precise
"levels solved" win in Phase 2.

The generator never solves Sokoban: it only reads the bundled level manifest
(``corpus.py`` / ``data/microban.json``) for counts and names.
"""

from __future__ import annotations

from typing import Any

from BaseClasses import LocationProgressType, Region
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
    assign_levels_by_difficulty,
    boss_world_index,
    chunk_levels,
    clamp,
    escape_valve_counts,
    solve_count_keys_needed,
)
from .Locations import (
    SokopelagoLocation,
    location_name_to_id,
    location_table,
    par_location_name,
    par_location_table,
    solve_location_name,
)
from .Options import SokopelagoOptions


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
    goal_solve_count: int
    boss_level: int
    expert: bool
    pull_levels: set[int]  # seed levels hard-gated behind the Pull ability (expert only)

    def generate_early(self) -> None:
        self.corpus_data = load_corpus_data(self.options.corpus.current_key)
        self.level_count = clamp(self.options.level_count.value, 5, self.corpus_data.count)
        self.levels_per_region = clamp(self.options.levels_per_region.value, 1, self.level_count)
        levels = list(range(1, self.level_count + 1))
        if self.options.difficulty_ordering.value and self.corpus_data.difficulty_by_n:
            self.worlds = assign_levels_by_difficulty(levels, self.corpus_data.difficulty_by_n, self.levels_per_region)
        else:
            self.worlds = chunk_levels(self.level_count, self.levels_per_region)
        self.region_count = len(self.worlds)
        self.goal_solve_count = clamp(self.options.goal_solve_count.value, 1, self.level_count)
        raw_boss = self.options.goal_boss_level.value
        self.boss_level = self.level_count if raw_boss == 0 else clamp(raw_boss, 1, self.level_count)
        # Expert Logic: hard-gate the seed's pull-required levels behind the Pull item.
        self.expert = bool(self.options.expert_logic.value)
        self.pull_levels = {n for n in levels if n in self.corpus_data.requires_pull} if self.expert else set()

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        par_checks = bool(self.options.par_checks.value)
        for i, level_ns in enumerate(self.worlds, start=1):
            region = Region(f"World {i}", self.player, self.multiworld)
            for n in level_ns:
                loc_name = solve_location_name(n)
                loc = SokopelagoLocation(self.player, loc_name, location_table[loc_name], region)
                self._apply_pull_gate(loc, n)
                region.locations.append(loc)
                if par_checks:
                    # The par location shares the region's key gate, but is EXCLUDED so
                    # only filler lands there — a hard par requirement (which escape
                    # valves can't bypass) can never strand a progression item.
                    par_name = par_location_name(n)
                    par_loc = SokopelagoLocation(self.player, par_name, par_location_table[par_name], region)
                    par_loc.progress_type = LocationProgressType.EXCLUDED
                    self._apply_pull_gate(par_loc, n)
                    region.locations.append(par_loc)
            self.multiworld.regions.append(region)

            if i == 1:
                menu.connect(region, f"Menu -> World {i}")
            else:
                key = world_key_name(i)
                menu.connect(
                    region,
                    f"Menu -> World {i}",
                    rule=lambda state, key=key: state.has(key, self.player),
                )

    def _apply_pull_gate(self, loc: SokopelagoLocation, n: int) -> None:
        """Gate a pull-required level's location behind the Pull item (expert logic)."""
        if n in self.pull_levels:
            loc.access_rule = lambda state, p=self.player: state.has(PULL_NAME, p)

    def create_items(self) -> None:
        keys: list[SokopelagoItem] = [self.create_item(world_key_name(n)) for n in range(2, self.region_count + 1)]
        # Expert Logic adds one Pull ability (progression) that gates the pull-required
        # levels. Like the keys it's a fixed progression item; it's carved from the budget
        # so the pool size stays exactly the location count.
        abilities: list[SokopelagoItem] = [self.create_item(PULL_NAME)] if self.pull_levels else []
        # One item per location. Par Checks adds a second (EXCLUDED) location per level,
        # so the pool must grow to match; the extra slots are plain filler.
        total_locations = self.level_count * (2 if self.options.par_checks.value else 1)
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
        """Wrap a key-based completion rule, ANDing in Pull when expert logic gates levels
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
            final_key = world_key_name(self.region_count)
            single = self.region_count <= 1
            cc[player] = self._completion((lambda s: True) if single else (lambda s, key=final_key: s.has(key, player)))

    def create_item(self, name: str) -> SokopelagoItem:
        data = item_table[name]
        return SokopelagoItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return FILLER_NAME

    def fill_slot_data(self) -> dict[str, Any]:
        seed_levels = [n for world in self.worlds for n in world]
        par_by_n = self.corpus_data.par_by_n
        difficulty_by_n = self.corpus_data.difficulty_by_n
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
            # When on, the client sends the parallel par-location check for any level
            # solved within its push-par (Phase 4 check density).
            "par_checks": bool(self.options.par_checks.value),
            # Expert Logic (Phase 5): when on, the client requires the Pull item before
            # the listed levels can be played; requires_pull maps those level numbers.
            "expert_logic": self.expert,
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
