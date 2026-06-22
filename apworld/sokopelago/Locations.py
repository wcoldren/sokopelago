"""Location definitions for Sokopelago.

Up to three locations per corpus level:
  * "Solve Microban n"                    — always present.
  * "Solve Microban n in <= par pushes"   — the *perfect* tier, added only when the Par
    Checks option is on (Phase 4 check density). Sends when solved in the optimal push
    count. Lives in a parallel id band (``PAR_LOC_ID_BASE + n``).
  * "Solve Microban n efficiently"        — the *efficient* tier, added only when the
    Efficiency Checks option is on (and Par Checks too). Sends when solved within a
    configurable margin over optimal — a gettable reward below the perfect tier. Lives
    in its own id band (``EFF_LOC_ID_BASE + n``).

Each band mirrors the solve band's ``+ n`` offset, so they stay symmetric and survive
any future change to the corpus size. Locations are keyed by Microban number (from the
bundled manifest) so IDs stay stable regardless of subtitle text or how many levels a
given seed actually uses. A seed attaches only its selected subset to its regions.
"""

from __future__ import annotations

from BaseClasses import Location

from .corpus import LOCATION_MAX

LOC_ID_BASE = 9_760_000  # "Solve Microban n" -> LOC_ID_BASE + n
PAR_LOC_ID_BASE = 9_770_000  # "Solve Microban n in <= par pushes" -> PAR_LOC_ID_BASE + n
EFF_LOC_ID_BASE = 9_780_000  # "Solve Microban n efficiently" -> EFF_LOC_ID_BASE + n


class SokopelagoLocation(Location):
    game: str = "Sokopelago"


def solve_location_name(n: int) -> str:
    return f"Solve Microban {n}"


def par_location_name(n: int) -> str:
    return f"Solve Microban {n} in <= par pushes"


def eff_location_name(n: int) -> str:
    return f"Solve Microban {n} efficiently"


# Register a fixed id for every level number 1..LOCATION_MAX (not just the Microban corpus), so any
# corpus up to that size — e.g. a large merged pool — has its "Solve … n" locations available. The
# ids for 1..155 are unchanged, so this only adds entries and never breaks an existing seed.
_NS = range(1, LOCATION_MAX + 1)
location_table: dict[str, int] = {solve_location_name(n): LOC_ID_BASE + n for n in _NS}
par_location_table: dict[str, int] = {par_location_name(n): PAR_LOC_ID_BASE + n for n in _NS}
eff_location_table: dict[str, int] = {eff_location_name(n): EFF_LOC_ID_BASE + n for n in _NS}

# All bands are registered so location_name_to_id is stable regardless of the per-seed
# Par Checks / Efficiency Checks toggles (Archipelago requires a fixed name->id map).
location_name_to_id: dict[str, int] = {**location_table, **par_location_table, **eff_location_table}
