"""Location definitions for Sokopelago.

One location per corpus level: "Solve Microban n". Locations are keyed by Microban
number (from the bundled manifest) so IDs stay stable regardless of subtitle text or
how many levels a given seed actually uses. A seed attaches only the selected subset
(the first ``level_count`` levels) to its regions.
"""

from __future__ import annotations

import typing

from BaseClasses import Location

from .corpus import LEVELS

LOC_ID_BASE = 9_760_000  # "Solve Microban n" -> LOC_ID_BASE + n


class SokopelagoLocation(Location):
    game: str = "Sokopelago"


def solve_location_name(n: int) -> str:
    return f"Solve Microban {n}"


location_table: typing.Dict[str, int] = {
    solve_location_name(entry["n"]): LOC_ID_BASE + entry["n"] for entry in LEVELS
}

location_name_to_id: typing.Dict[str, int] = dict(location_table)
