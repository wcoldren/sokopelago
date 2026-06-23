#!/usr/bin/env python3
"""Fetch the Chu et al. (2025) human-rated Sokoban dataset for *dev-only* scorer calibration.

The dataset (442 puzzles with human like/dislike votes) accompanies:

    Chu, J., Zheng, K., & Fan, J. E. (2025). "What makes people think a puzzle is fun to
    solve?" Proceedings of the 47th Annual Conference of the Cognitive Science Society.
    https://escholarship.org/uc/item/9dm448rv  ·  CC BY 4.0
    Code/data: https://github.com/cogtoolslab/fun-puzzles_cogsci25

It is downloaded into the **gitignored** ``data/calibration/`` directory and used ONLY to
*report* how well our interpretable scorer tracks human ratings (see ``calibrate_scoring.py``).
It is never shipped as game content, never added to ``CORPUS_NAMES``, and never committed — the
puzzle boards themselves are community-authored (sourced via SokobanOnline's web archive) and are
not ours to vendor. Attribution is recorded per CC BY in the README this tool writes.

Run:  python tools/fetch_calibration.py
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from xsb_levels import REPO_ROOT

DEST_DIR = REPO_ROOT / "data" / "calibration"
DATASET_URL = (
    "https://raw.githubusercontent.com/cogtoolslab/fun-puzzles_cogsci25/master/data/study1/full_sokobanonline_df.csv"
)
DATASET_FILE = DEST_DIR / "full_sokobanonline_df.csv"

_README = """\
# Calibration data (dev-only, not shipped, gitignored)

Downloaded by `tools/fetch_calibration.py`. Used only to *report* how well Sokopelago's
interpretable scorer (`tools/scoring.py`) tracks human enjoyment ratings — a weak prior, not a
learned oracle. Not game content; never committed.

## Source & attribution (CC BY 4.0)

Chu, J., Zheng, K., & Fan, J. E. (2025). *What makes people think a puzzle is fun to solve?*
Proceedings of the 47th Annual Conference of the Cognitive Science Society.
- Paper: https://escholarship.org/uc/item/9dm448rv
- Code/data: https://github.com/cogtoolslab/fun-puzzles_cogsci25
- License: Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/)

442 puzzles / 4031 like-or-dislike votes. The puzzle boards were sourced by the authors from
SokobanOnline's "Web Archive"; they are community-authored and used here transiently for
calibration only — Sokopelago does not redistribute them.
"""


def fetch(force: bool = False) -> Path:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    (DEST_DIR / "README.md").write_text(_README, encoding="utf-8")
    if DATASET_FILE.exists() and not force:
        print(f"already present: {DATASET_FILE.relative_to(REPO_ROOT)} (use --force to refresh)")
        return DATASET_FILE
    req = urllib.request.Request(DATASET_URL, headers={"User-Agent": "sokopelago-calibration/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        DATASET_FILE.write_bytes(resp.read())
    print(f"fetched {DATASET_FILE.relative_to(REPO_ROOT)} ({DATASET_FILE.stat().st_size} bytes)")
    print("  next: python tools/calibrate_scoring.py")
    return DATASET_FILE


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    fetch(ap.parse_args().force)


if __name__ == "__main__":
    main()
