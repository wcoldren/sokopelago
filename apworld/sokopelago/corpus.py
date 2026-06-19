"""Loads the bundled level manifest (data/microban.json).

The manifest is produced offline by ``tools/build_corpus.py`` from the canonical
``levels/microban.xsb``. It is the static data table both the apworld and the client
consume — it carries level counts and display names, never solvability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, TypedDict


class LevelEntry(TypedDict):
    n: int
    name: str


_MANIFEST = Path(__file__).parent / "data" / "microban.json"

LEVELS: List[LevelEntry] = json.loads(_MANIFEST.read_text(encoding="utf-8"))
LEVEL_COUNT: int = len(LEVELS)
NAME_BY_N: Dict[int, str] = {entry["n"]: entry["name"] for entry in LEVELS}
