# Sokopelago apworld

The Archipelago world for Sokopelago. **Phase 0 status: stub only** — the package
`sokopelago/` is an empty, importable placeholder. The real world (items, locations,
regions, rules, options, slot_data) lands in **Phase 1**, modelled on
`worlds/checksfinder` in the Archipelago tree.

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

**Runner:** vanilla `vendor/Archipelago` (pinned 0.6.7). Sokopelago needs no engine
changes, so the Emerald fork is deliberately not the runner.

The symlink + first `Generate.py` run are **Phase 1** work. Phase 0 touches no clone.

## Level corpus

The world will read the same canonical corpus the client uses: `../levels/microban.xsb`
(Microban by David W. Skinner — see `../levels/ATTRIBUTION.md`).
