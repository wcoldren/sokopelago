<!-- GENERATED FILE — do not edit by hand.
     Rendered from levels/provenance.json by tools/provenance.py
     (regenerate: python tools/provenance.py --write-attribution). -->

# Level corpus attribution

Per-set provenance and redistribution terms for every bundled Sokoban corpus. The
machine-readable source of truth is [`provenance.json`](provenance.json); this file is
generated from it. A repo-level summary lives in [`../CREDITS.md`](../CREDITS.md).

## Microban (155 puzzles, revised April 2000) — `microban.xsb`

- **Author:** David W. Skinner
- **Source:** <https://www.onlinespiele-sammlung.de/sokoban/sokobangames/skinner/>
- **License:** `skinner-free-distribution-with-credit`

### Distribution terms

> These sets may be freely distributed provided they remain properly credited.

Required credit: *Microban by David W. Skinner.*

Vendored verbatim from the ShenMian/sokoban-rs collection (assets/levels/microban_155.xsb), which preserves Skinner's original file. The only change is a prepended attribution header (XSB ';' comments, ignored by every parser) so the credit travels with the corpus.

`sha256(levels/microban.xsb)` = `4f75d3a7101e4fd37d52d5801cf15eccb1f9e50f4f655e7ec27f432a5a180675`

## Pullban (30 original expert levels) — `pullban.xsb`

- **Author:** William Coldren
- **License:** `sokopelago-free-distribution-with-credit`
- **Original by construction** — no third-party puzzles; no external attribution required.

### Distribution terms

> Freely distributable with attribution, on the same terms as the bundled Microban set.

Required credit: *Pullban (original) by William Coldren, for Sokopelago.*

An original Sokopelago expert corpus for the Phase 5 ability tier: a mix of ordinary push levels and levels that require the Pull ability. Designed by William Coldren (2026); levels 11+ are machine-authored for this project, every board solver-verified. Adopts Microban's distribution terms but is original work owing no Skinner attribution.

`sha256(levels/pullban.xsb)` = `40ab04bd34bf84363fd2eb04816b554044894e47bda074d42a556d5398a79242`

## Autoban (generated corpus, v1.0.0, seed 0) — `autoban.xsb`

- **Author:** Sokopelago owned generator (tools/generate_corpus.py)
- **License:** `sokopelago-free-distribution-with-credit`
- **Original by construction** — no third-party puzzles; no external attribution required.

### Distribution terms

> Freely distributable with attribution, on the same terms as the bundled Microban set.

Required credit: *Autoban (generated) by the Sokopelago puzzle generator.*

Generated in-house by Sokopelago's own puzzle generator and original by construction: each level is built by reverse-construction (place every box on a goal, then scatter with legal pulls), so it contains no third-party puzzles and needs no external attribution. Difficulty is calibrated against Microban's native scale.

`sha256(levels/autoban.xsb)` = `95e2325c4ed64b0f91463118846bbe74ea5cafa8c52d40c81b89dfd17833de5e`

## Microban II (135 puzzles) — `microban2.xsb`

- **Author:** David W. Skinner
- **Source:** <https://www.onlinespiele-sammlung.de/sokoban/sokobangames/skinner/m2.txt>
- **License:** `skinner-free-distribution-with-credit`

### Distribution terms

> These sets may be freely distributed provided they remain properly credited.

Required credit: *Microban II (135 puzzles) by David W. Skinner.*

Downloaded from the canonical Skinner mirror (https://www.onlinespiele-sammlung.de/sokoban/sokobangames/skinner/m2.txt). XSB text with no per-file credit; an attribution header is prepended on ingest.

`sha256(levels/microban2.xsb)` = `c7e200f4608ae3984505e2aa8a5ad9b58bd11bc20ad6e4140c45a8e874b13787`

## XSokoban (90 levels) — `xsokoban90.xsb`

- **Author:** XSokoban project (Joseph L. Traub, Andrew Myers, et al.)
- **Source:** <https://github.com/andrewcmyers/xsokoban>
- **License:** `public-domain`

### Distribution terms

> XSokoban is distributed in the public domain and may be freely redistributed.

Required credit: *XSokoban (public domain).*

Concatenated from screens/screen.1..90 in https://github.com/andrewcmyers/xsokoban (public domain). Each screen is one board; a '; N' title is added per level on ingest.

`sha256(levels/xsokoban90.xsb)` = `10cc5b589c60c7cc50d34ba8725af8ef14fe26664fa06c4fb79cf921779b4678`
