"""Base test class for Sokopelago, run against a real Archipelago install.

When the apworld is symlinked into an AP clone as ``worlds/sokopelago``, this module
is importable as ``worlds.sokopelago.test.bases`` and the absolute ``from test.bases``
resolves to AP's own top-level test package (the standard world-test idiom).

The class name deliberately does NOT start with ``Test`` so pytest does not collect the
bare base; concrete ``Test*`` subclasses live in the sibling test modules.
"""

from typing import Optional

from test.bases import WorldTestBase

# Options whose 0.6 defaults reshape level selection / world layout. The existing Test*
# subclasses predate them and assume the whole corpus is eligible in its native layout,
# so default them to the legacy behavior unless a subclass opts in. (An unknown key is
# ignored by world_setup, so listing gentle_first_world here is safe even before/after
# the option exists.)
_LEGACY_OPTION_DEFAULTS = {"max_difficulty": "any", "gentle_first_world": 0}


class SokopelagoTestBase(WorldTestBase):
    game = "Sokopelago"

    def world_setup(self, seed: Optional[int] = None) -> None:
        merged = dict(self.options)
        for key, value in _LEGACY_OPTION_DEFAULTS.items():
            merged.setdefault(key, value)
        self.options = merged  # instance attr; the class attr (shared) is left intact
        super().world_setup(seed)
