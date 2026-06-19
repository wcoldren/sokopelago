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

from typing import Any, Dict, List

from BaseClasses import Region
from worlds.AutoWorld import WebWorld, World

from .corpus import LEVEL_COUNT
from .Items import FILLER_NAME, SokopelagoItem, item_table, item_name_to_id, world_key_name
from .Locations import SokopelagoLocation, location_name_to_id, location_table, solve_location_name
from .layout import boss_world_index, chunk_levels, clamp, solve_count_keys_needed
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
    worlds: List[List[int]]
    region_count: int
    level_count: int
    levels_per_region: int
    goal_solve_count: int
    boss_level: int

    def generate_early(self) -> None:
        self.level_count = clamp(self.options.level_count.value, 5, LEVEL_COUNT)
        self.levels_per_region = clamp(self.options.levels_per_region.value, 1, self.level_count)
        self.worlds = chunk_levels(self.level_count, self.levels_per_region)
        self.region_count = len(self.worlds)
        self.goal_solve_count = clamp(self.options.goal_solve_count.value, 1, self.level_count)
        raw_boss = self.options.goal_boss_level.value
        self.boss_level = self.level_count if raw_boss == 0 else clamp(raw_boss, 1, self.level_count)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        for i, level_ns in enumerate(self.worlds, start=1):
            region = Region(f"World {i}", self.player, self.multiworld)
            for n in level_ns:
                loc_name = solve_location_name(n)
                region.locations.append(
                    SokopelagoLocation(self.player, loc_name, location_table[loc_name], region)
                )
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

    def create_items(self) -> None:
        itempool: List[SokopelagoItem] = [
            self.create_item(world_key_name(n)) for n in range(2, self.region_count + 1)
        ]
        filler_needed = self.level_count - len(itempool)
        itempool += [self.create_filler() for _ in range(filler_needed)]
        self.multiworld.itempool += itempool

    def set_rules(self) -> None:
        player = self.player
        goal = self.options.goal
        all_keys = [world_key_name(n) for n in range(2, self.region_count + 1)]

        if goal == "solve_count":
            world_sizes = [len(w) for w in self.worlds]
            k = solve_count_keys_needed(world_sizes, self.goal_solve_count)
            if k == 0:
                self.multiworld.completion_condition[player] = lambda state: True
            else:
                self.multiworld.completion_condition[player] = (
                    lambda state: state.has_from_list(all_keys, player, k)
                )
        elif goal == "boss_level":
            bw = boss_world_index(self.worlds, self.boss_level)
            if bw == 1:
                self.multiworld.completion_condition[player] = lambda state: True
            else:
                key = world_key_name(bw)
                self.multiworld.completion_condition[player] = lambda state: state.has(key, player)
        else:  # beat_final_region
            if self.region_count <= 1:
                self.multiworld.completion_condition[player] = lambda state: True
            else:
                key = world_key_name(self.region_count)
                self.multiworld.completion_condition[player] = lambda state: state.has(key, player)

    def create_item(self, name: str) -> SokopelagoItem:
        data = item_table[name]
        return SokopelagoItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return FILLER_NAME

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "corpus": "microban",
            "level_count": self.level_count,
            "levels_per_region": self.levels_per_region,
            "levels": [n for world in self.worlds for n in world],
            "region_map": {str(i): world for i, world in enumerate(self.worlds, start=1)},
            "goal": self.options.goal.current_key,
            "goal_solve_count": self.goal_solve_count,
            "goal_boss_level": self.boss_level,
            "final_world": self.region_count,
            "seed_name": self.multiworld.seed_name,
            "player_name": self.player_name,
            "player_id": self.player,
        }
