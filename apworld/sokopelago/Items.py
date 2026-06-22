"""Item definitions for Sokopelago.

Items:
  * "World n Key"  (progression) — opens region n (worlds 2..N; World 1 is free).
  * "Sokoban Token" (filler)     — pads the pool to the location count.
  * Escape valves (Phase 3, useful) — "Skip Token", "Undo Charge", "Hint Token".
  * Traps (Phase 3, trap)        — "Trap: …" presentation/control annoyances.

IDs are arbitrary per-world integers (see BaseClasses ID range). Keys are keyed by
world number so they stay stable as options change the number of worlds in a seed.
The escape-valve / trap ids sit in a band well clear of the key range
(``KEY_ID_BASE + 2..155``) and the location range (``9_760_000+``). None of the
Phase 3 items are progression, so access logic and beatability are unaffected; they
are carved out of the filler budget so the pool size never changes.
"""

from __future__ import annotations

import typing

from BaseClasses import Item, ItemClassification

# Max worlds = max keyed worlds. Keys are KEY_ID_BASE + n (n in 2..MAX_WORLDS); the escape-valve
# band starts at KEY_ID_BASE + 200 (SKIP_ID 9_750_200), so MAX_WORLDS must stay < 200 to keep the
# key ids clear of it. 198 leaves a margin and covers any realistic worlds-per-seed (a large merged
# pool at levels_per_region >= ~3). Raising it only adds key ids 156..198 — backward-compatible.
MAX_WORLDS = 198

KEY_ID_BASE = 9_750_000  # "World n Key" -> KEY_ID_BASE + n  (n in 2..MAX_WORLDS)
FILLER_ID = 9_750_001  # n == 1 slot is unused (World 1 is free), so this is free.

FILLER_NAME = "Sokoban Token"

# Escape valves (band 9_750_200+, clear of keys at +2..+155).
SKIP_NAME = "Skip Token"
UNDO_NAME = "Undo Charge"
HINT_NAME = "Hint Token"
SKIP_ID = 9_750_200
UNDO_ID = 9_750_201
HINT_ID = 9_750_202

# Maps the layout helper's valve keys to item names (traps handled separately).
VALVE_ITEM_NAMES: dict[str, str] = {"skip": SKIP_NAME, "undo": UNDO_NAME, "hint": HINT_NAME}

# Trap variants (band 9_750_300+). Distinct ids so spoilers / item-received messages
# name the specific trap; the client resolves each to its (presentation-only) effect.
TRAP_ID_BASE = 9_750_300
TRAP_ITEM_NAMES: list[str] = ["Trap: Scramble", "Trap: Decoy Box", "Trap: Reversed Controls"]

# Ability items (band 9_750_400+). Unlike the Phase 3 valves, these ARE progression: an
# ability hard-gates the levels that require it under the Expert Logic option (Phase 5).
ABILITY_ID_BASE = 9_750_400
PULL_NAME = "Pull"
PULL_ID = 9_750_400


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
item_table[SKIP_NAME] = ItemData(SKIP_ID, ItemClassification.useful)
item_table[UNDO_NAME] = ItemData(UNDO_ID, ItemClassification.useful)
item_table[HINT_NAME] = ItemData(HINT_ID, ItemClassification.useful)
for _i, _trap in enumerate(TRAP_ITEM_NAMES):
    item_table[_trap] = ItemData(TRAP_ID_BASE + _i, ItemClassification.trap)
item_table[PULL_NAME] = ItemData(PULL_ID, ItemClassification.progression)

item_name_to_id: dict[str, int] = {name: data.code for name, data in item_table.items()}
