# Sokopelago apworld

The Archipelago world for Sokopelago. The package `sokopelago/` implements the full
world — items, locations, regions, rules, options, and slot_data — modelled on
`worlds/checksfinder` in the Archipelago tree. Current version `0.8.1` (Phases 0–5 + accurate
logic + cross-corpus pools; see the repo-root [CHANGELOG.md](../CHANGELOG.md) and
[VERSIONING.md](../VERSIONING.md)).

## Integration model (independent repo + symlink, never a fork)

Sokopelago stays its own git repo. The world is bridged into a **vanilla Archipelago
clone** by symlinking this package into the clone's `worlds/` — it is *not* copied or
vendored into any Archipelago fork (e.g. the Emerald `archem` fork).

```sh
# from the AP workspace root (paths are illustrative)
ln -s "$PWD/vendor/sokopelago/apworld/sokopelago" \
      "$PWD/vendor/Archipelago/worlds/sokopelago"
# keep the clone pristine — exclude the symlink locally (worlds/ is a tracked dir):
echo worlds/sokopelago >> "$PWD/vendor/Archipelago/.git/info/exclude"
```

Why `worlds/`, not `custom_worlds/` (this matters on 0.6.7):

- The loader (`worlds/__init__.py`) imports every **unpacked** source directory as
  `worlds.<name>` (`importlib.import_module(".<name>", "worlds")`). The `worlds` package
  `__path__` is only the `worlds/` folder, so an unpacked dir symlinked into
  `custom_worlds/` fails to import (ModuleNotFoundError, logged and skipped). `custom_worlds/`
  auto-loads only **packed `.apworld` zips** (a separate zipimport finder).
- A live-editable source symlink therefore must live under `worlds/`. `.git/info/exclude`
  is local-only and untracked, so the clone's committed files stay pristine.
- Package names can't start with `.` or `_`; `sokopelago` is fine.

The repo-root `./playtest.sh` creates this symlink for you if it's missing.

**Runner:** vanilla `vendor/Archipelago` (pinned 0.6.7, matching `minimum_ap_version` in
`sokopelago/archipelago.json`). Sokopelago needs no engine changes, so the Emerald fork
is deliberately not the runner.

## Level corpus

The world will read the same canonical corpus the client uses: `../levels/microban.xsb`
(Microban by David W. Skinner — see `../levels/ATTRIBUTION.md`).
