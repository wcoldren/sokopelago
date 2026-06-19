"""Base test class for Sokopelago, run against a real Archipelago install.

When the apworld is symlinked into an AP clone as ``worlds/sokopelago``, this module
is importable as ``worlds.sokopelago.test.bases`` and the absolute ``from test.bases``
resolves to AP's own top-level test package (the standard world-test idiom).

The class name deliberately does NOT start with ``Test`` so pytest does not collect the
bare base; concrete ``Test*`` subclasses live in the sibling test modules.
"""

from test.bases import WorldTestBase


class SokopelagoTestBase(WorldTestBase):
    game = "Sokopelago"
