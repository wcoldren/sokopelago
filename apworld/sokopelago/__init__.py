"""Sokopelago — Archipelago world (Phase 1 stub).

Phase 0 ships only the local browser client and the level corpus; this package is
an intentionally empty, importable home so the Phase 1 world drops in cleanly.

Phase 1 will define, modelled on ``worlds/checksfinder`` in the Archipelago tree:

* ``Items.py``   — region keys (progression) + filler.
* ``Locations.py`` — one location per level (``Solve <level>``).
* ``Options.py`` — corpus selection, number of levels, goal type.
* ``__init__.py`` — the ``World`` subclass: ``create_regions`` (worlds gated by
  keys, levels as locations inside), ``create_items``, ``set_rules`` (a location is
  reachable iff its region key is held — standard region-access logic), and
  ``fill_slot_data`` (which levels are in the seed, the region->level map, the goal).

Hard constraint (see ../../ROADMAP.md): the generator must never solve Sokoban.
All solvability facts are precomputed offline into a static table that both this
world and the client consume.

Integration is via a symlink into a vanilla Archipelago clone's ``custom_worlds/``
(see ../README.md) — Sokopelago is never vendored inside an Archipelago fork.
"""
