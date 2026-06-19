"""Item definitions for Sokopelago.

Phase 1 items:
  * "World n Key" (progression) — opens region n (worlds 2..N; World 1 is free).
  * "Sokoban Token" (filler)     — pads the pool to the location count.

IDs are arbitrary per-world integers (see BaseClasses ID range). Keys are keyed by
world number so they stay stable as options change the number of worlds in a seed.
Escape-valve filler (skip tokens, hints, undo) arrives in Phase 3.
"""

from __future__ import annotations

import typing

from BaseClasses import Item, ItemClassification

# Microban has 155 levels, so at most 155 worlds (levels_per_region == 1).
MAX_WORLDS = 155

KEY_ID_BASE = 9_750_000  # "World n Key" -> KEY_ID_BASE + n  (n in 2..MAX_WORLDS)
FILLER_ID = 9_750_001  # n == 1 slot is unused (World 1 is free), so this is free.

FILLER_NAME = "Sokoban Token"


class ItemData(typing.NamedTuple):
    code: int
    classification: ItemClassification


class SokopelagoItem(Item):
    game: str = "Sokopelago"


def world_key_name(n: int) -> str:
    return f"World {n} Key"


item_table: dict[str, ItemData] = {
    world_key_name(n): ItemData(KEY_ID_BASE + n, ItemClassification.progression) for n in range(2, MAX_WORLDS + 1)
}
item_table[FILLER_NAME] = ItemData(FILLER_ID, ItemClassification.filler)

item_name_to_id: dict[str, int] = {name: data.code for name, data in item_table.items()}
