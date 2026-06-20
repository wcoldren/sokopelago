# Sokopelago apworld

The Archipelago world for Sokopelago. The package `sokopelago/` implements the full
world — items, locations, regions, rules, options, and slot_data — modelled on
`worlds/checksfinder` in the Archipelago tree. Current version `0.4.0` (Phases 0–5; see
the repo-root [CHANGELOG.md](../CHANGELOG.md) and [VERSIONING.md](../VERSIONING.md)).

## Integration model (independent repo + symlink, never a fork)

Sokopelago stays its own git repo. The world is bridged into a **vanilla Archipelago
clone** by symlinking this package into the clone's `custom_worlds/` — it is *not*
copied or vendored into any Archipelago fork (e.g. the Emerald `archem` fork).

```sh
# from the AP workspace root (paths are illustrative)
ln -s "$PWD/vendor/sokopelago/apworld/sokopelago" \
      "$PWD/vendor/Archipelago/custom_worlds/sokopelago"
```

Why this works and stays clean:

- `custom_worlds/` is **already gitignored** in the Archipelago clone, so the symlink
  is invisible to git — no `.git/info/exclude` step, and the clone stays pristine.
- Archipelago's loader (`worlds/__init__.py`) scans both `worlds/` and `custom_worlds/`
  and loads **unpacked package directories via symlink** (`os.scandir` follows the
  link and matches `entry.is_dir()`), so this stays live-editable from source.
- Package names can't start with `.` or `_`; `sokopelago` is fine.

**Runner:** vanilla `vendor/Archipelago` (pinned 0.6.7, matching `minimum_ap_version` in
`sokopelago/archipelago.json`). Sokopelago needs no engine changes, so the Emerald fork
is deliberately not the runner.

## Level corpus

The world will read the same canonical corpus the client uses: `../levels/microban.xsb`
(Microban by David W. Skinner — see `../levels/ATTRIBUTION.md`).
