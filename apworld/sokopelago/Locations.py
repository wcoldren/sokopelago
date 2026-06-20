"""Location definitions for Sokopelago.

Up to two locations per corpus level:
  * "Solve Microban n"                    — always present.
  * "Solve Microban n in <= par pushes"   — added only when the Par Checks option is
    on (Phase 4 check density). It lives in a parallel id band (``PAR_LOC_ID_BASE + n``)
    that mirrors the solve band's ``+ n`` offset, so the two stay symmetric and survive
    any future change to the corpus size.

Locations are keyed by Microban number (from the bundled manifest) so IDs stay stable
regardless of subtitle text or how many levels a given seed actually uses. A seed
attaches only the selected subset (the first ``level_count`` levels) to its regions.
"""

from __future__ import annotations

from BaseClasses import Location

from .corpus import LEVELS

LOC_ID_BASE = 9_760_000  # "Solve Microban n" -> LOC_ID_BASE + n
PAR_LOC_ID_BASE = 9_770_000  # "Solve Microban n in <= par pushes" -> PAR_LOC_ID_BASE + n


class SokopelagoLocation(Location):
    game: str = "Sokopelago"


def solve_location_name(n: int) -> str:
    return f"Solve Microban {n}"


def par_location_name(n: int) -> str:
    return f"Solve Microban {n} in <= par pushes"


location_table: dict[str, int] = {solve_location_name(entry["n"]): LOC_ID_BASE + entry["n"] for entry in LEVELS}
par_location_table: dict[str, int] = {par_location_name(entry["n"]): PAR_LOC_ID_BASE + entry["n"] for entry in LEVELS}

# Both bands are registered so location_name_to_id is stable regardless of the per-seed
# Par Checks toggle (Archipelago requires a fixed name->id map for the world).
location_name_to_id: dict[str, int] = {**location_table, **par_location_table}
