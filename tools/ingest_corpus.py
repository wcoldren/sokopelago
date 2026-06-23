#!/usr/bin/env python3
"""Ingest a freely-licensed Sokoban set: fetch -> parse -> canonicalize/dedup -> register.

Downloads are gated to an :data:`APPROVED_SOURCES` allowlist (each entry carries its license +
required attribution), so this tool can only ever fetch sources whose redistribution terms are
recorded. The flow per source:

  fetch (allowlisted URL, dev cache)  ->  parse XSB/SOK to Level objects (fail closed on any
  unrecognized glyph)  ->  dedup within the set AND across existing corpora via the shared
  reachability-aware canonical key  ->  write levels/<corpus>.xsb (attribution header prepended)
  ->  register a provenance entry + regenerate ATTRIBUTION.md.

Solving/scoring is a separate stage — run ``tools/annotate_corpus.py --corpus <name>`` afterward.

Run:  python tools/ingest_corpus.py --list
      python tools/ingest_corpus.py --corpus microban2 --dry-run     # fetch+parse+dedup report
      python tools/ingest_corpus.py --corpus microban2               # writes + registers
"""

from __future__ import annotations

import argparse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import provenance
from canonical import canonical_player_normalized
from xsb_levels import CORPORA, REPO_ROOT, is_board_row, parse_levels

CACHE_DIR = REPO_ROOT / ".ingest-cache"  # gitignored dev cache of raw downloads
_VALID_GLYPHS = set("#@+$*. ")
_STRUCTURAL = set("#$*@+")  # a line with one of these is meant to be a board row

# --------------------------------------------------------------------------------------
# Approved sources (the ONLY URLs this tool will fetch). Each carries its provenance.
# --------------------------------------------------------------------------------------
_SKINNER_BASE = "https://www.onlinespiele-sammlung.de/sokoban/sokobangames/skinner/"
_SKINNER_TERMS = "These sets may be freely distributed provided they remain properly credited."
_XSOKOBAN_REPO = "https://github.com/andrewcmyers/xsokoban"


def _skinner(corpus: str, filename: str, source_name: str) -> dict:
    return {
        "corpus": corpus,
        "url": _SKINNER_BASE + filename,
        "fmt": "xsb",
        "source_name": source_name,
        "author": "David W. Skinner",
        "license_id": "skinner-free-distribution-with-credit",
        "license_url": None,
        "distribution_terms": _SKINNER_TERMS,
        "attribution_required": f"{source_name} by David W. Skinner.",
        "original_by_construction": False,
        "notes": f"Downloaded from the canonical Skinner mirror ({_SKINNER_BASE}{filename}). "
        "XSB text with no per-file credit; an attribution header is prepended on ingest.",
    }


# Sasquatch set display names as the mirror lists them.
_SASQUATCH_NAMES = {
    1: "Sasquatch (50 puzzles)",
    2: "Mas Sasquatch (50 puzzles)",
    3: "Sasquatch III (50 puzzles)",
    4: "Sasquatch IV (50 puzzles)",
    5: "Sasquatch V (50 puzzles)",
    6: "Sasquatch VI (50 puzzles)",
    7: "Sasquatch VII (50 puzzles)",
    8: "Sasquatch VIII (50 puzzles)",
    9: "Sasquatch IX (50 puzzles)",
}

APPROVED_SOURCES: dict[str, dict] = {
    # Microban I is already vendored (levels/microban.xsb). These are the further Skinner sets
    # hosted on the canonical free-distribution mirror (Microban IV/V are NOT on it).
    "microban2": _skinner("microban2", "m2.txt", "Microban II (135 puzzles)"),
    "microban3": _skinner("microban3", "m3.txt", "Microban III (64 puzzles)"),
}
for _i, _name in _SASQUATCH_NAMES.items():
    APPROVED_SOURCES[f"sasquatch{_i}"] = _skinner(f"sasquatch{_i}", f"s{_i}.txt", _name)

APPROVED_SOURCES["xsokoban90"] = {
    "corpus": "xsokoban90",
    "url_template": "https://raw.githubusercontent.com/andrewcmyers/xsokoban/master/screens/screen.{}",
    "index_range": (1, 90),
    "fmt": "xsb",
    "source_name": "XSokoban (90 levels)",
    "author": "XSokoban project (Joseph L. Traub, Andrew Myers, et al.)",
    "license_id": "public-domain",
    "license_url": None,
    "distribution_terms": "XSokoban is distributed in the public domain and may be freely redistributed.",
    "attribution_required": "XSokoban (public domain).",
    "original_by_construction": False,
    "notes": f"Concatenated from screens/screen.1..90 in {_XSOKOBAN_REPO} (public domain). "
    "Each screen is one board; a '; N' title is added per level on ingest.",
}


# --------------------------------------------------------------------------------------
# Fetch (allowlist-gated)
# --------------------------------------------------------------------------------------
def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "sokopelago-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def fetch_source(source: dict, *, cache_dir: Path = CACHE_DIR, force: bool = False) -> str:
    """Download an approved source to the dev cache and return its raw text. Numbered sources
    (XSokoban screens) are fetched per file and concatenated with ``; N`` titles."""
    if APPROVED_SOURCES.get(source["corpus"]) is not source:
        raise SystemExit(f"refusing to fetch un-allowlisted source: {source.get('corpus')!r}")
    cache = cache_dir / f"{source['corpus']}.raw.xsb"
    if cache.exists() and not force:
        return cache.read_text(encoding="utf-8")
    if "url_template" in source:
        lo, hi = source["index_range"]
        parts = [f"; {i}\n\n{_http_get(source['url_template'].format(i)).rstrip()}\n" for i in range(lo, hi + 1)]
        text = "\n".join(parts)
    else:
        text = _http_get(source["url"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


# --------------------------------------------------------------------------------------
# Parse (fail closed on unrecognized glyphs)
# --------------------------------------------------------------------------------------
def parse_source(text: str, fmt: str = "auto") -> list:
    """Parse XSB/SOK collection text into Levels, normalizing ``_``->space and FAILING LOUDLY on
    any board-looking line with an unrecognized glyph (so a near-board line is never silently
    dropped as a separator). RLE-compressed SOK is not supported — its digits trip this guard."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # normalize CRLF and bare-CR (old-Mac, e.g. Sasquatch VIII)
    norm_lines = []
    for raw in text.split("\n"):
        line = raw.rstrip("\r").replace("_", " ")
        if set(line) & _STRUCTURAL and not is_board_row(line):
            bad = sorted(set(line) - _VALID_GLYPHS)
            raise ValueError(f"unrecognized glyph(s) {bad} in board line: {line!r}")
        norm_lines.append(line)
    return parse_levels("\n".join(norm_lines))


# --------------------------------------------------------------------------------------
# Dedup (within-set + cross-set via the reachability-aware canonical key)
# --------------------------------------------------------------------------------------
def _seen_from(corpora: tuple[str, ...]) -> dict[str, str]:
    """canonical_player_normalized key -> source corpus, for every level in ``corpora`` that
    is present on disk (missing corpora skipped)."""
    from xsb_levels import load_corpus  # local: avoids importing the loader at module load

    seen: dict[str, str] = {}
    for name in corpora:
        path = CORPORA.get(name)
        if not path or not path.exists():
            continue
        for lvl in load_corpus(path):
            seen.setdefault(canonical_player_normalized(lvl), name)
    return seen


def dedup_levels(levels: list, against: tuple[str, ...]) -> tuple[list, list[dict]]:
    """Return (kept, dropped). A level is dropped if dihedral/player-equivalent to one already
    kept in this set (reason ``dup-within``) or present in an ``against`` corpus (``dup-vs-<c>``)."""
    seen = _seen_from(against)
    within: dict[str, int] = {}
    kept, dropped = [], []
    for lvl in levels:
        key = canonical_player_normalized(lvl)
        if key in seen:
            dropped.append({"n": lvl.n, "reason": f"dup-vs-{seen[key]}"})
        elif key in within:
            dropped.append({"n": lvl.n, "reason": f"dup-within (== n{within[key]})"})
        else:
            within[key] = lvl.n
            kept.append(lvl)
    return kept, dropped


# --------------------------------------------------------------------------------------
# Write + register
# --------------------------------------------------------------------------------------
def _attribution_header(source: dict) -> str:
    src = source.get("url") or source.get("url_template", "").format("N")
    lines = [
        "; " + "=" * 75,
        f"; {source['source_name']} — by {source['author']}.",
        f'; Bundled by Sokopelago. Distribution terms: "{source["distribution_terms"]}"',
        f"; Source: {src}",
        "; (Lines starting with ';' are XSB comments, ignored by the level parsers.)",
        "; " + "=" * 75,
    ]
    return "\n".join(lines) + "\n"


def write_xsb(corpus: str, levels: list, source: dict) -> Path:
    """Render ``levels`` (renumbered 1..k, boards verbatim) to ``levels/<corpus>.xsb`` with a
    prepended attribution comment header so the credit travels with the file."""
    out = REPO_ROOT / "levels" / f"{corpus}.xsb"
    body = [_attribution_header(source)]
    for i, lvl in enumerate(levels, 1):
        body.append(f"\n; {i}\n\n" + "\n".join(lvl.rows) + "\n")
    out.write_text("".join(body), encoding="utf-8")
    return out


def register_corpus(corpus: str, xsb_path: Path, source: dict) -> None:
    """Write the machine-readable provenance entry (with retrieval time + xsb digest) and
    regenerate ATTRIBUTION.md from the registry."""
    prov = {
        "corpus": corpus,
        "source_name": source["source_name"],
        "author": source["author"],
        "source_url": source.get("url") or _XSOKOBAN_REPO,
        "license_id": source["license_id"],
        "license_url": source.get("license_url"),
        "distribution_terms": source["distribution_terms"],
        "attribution_required": source.get("attribution_required"),
        "redistributable": True,
        "original_by_construction": source.get("original_by_construction", False),
        "notes": source.get("notes"),
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256_xsb": provenance.sha256_of(xsb_path),
    }
    provenance.upsert(corpus, prov)
    CORPORA.setdefault(corpus, xsb_path)
    provenance.write_attribution_md()


def ingest(
    corpus: str, *, against: tuple[str, ...], cache_dir: Path = CACHE_DIR, force: bool = False, write: bool = True
) -> dict:
    """Fetch -> parse -> dedup -> (optionally) write+register one approved source. Returns a summary."""
    source = APPROVED_SOURCES.get(corpus)
    if source is None:
        raise SystemExit(f"{corpus!r} is not in APPROVED_SOURCES (use --list)")
    text = fetch_source(source, cache_dir=cache_dir, force=force)
    levels = parse_source(text, source.get("fmt", "auto"))
    kept, dropped = dedup_levels(levels, against)
    summary = {"corpus": corpus, "parsed": len(levels), "kept": len(kept), "dropped": len(dropped), "drops": dropped}
    if write:
        xsb_path = write_xsb(corpus, kept, source)
        register_corpus(corpus, xsb_path, source)
        print(f"ingested {len(kept)} levels (dropped {len(dropped)} dup) -> {xsb_path.relative_to(REPO_ROOT)}")
        print(f"  registered provenance for {corpus!r}; next: python tools/annotate_corpus.py --corpus {corpus}")
    else:
        print(f"[dry-run] {corpus}: parsed={len(levels)} kept={len(kept)} dropped={len(dropped)}")
        for d in dropped[:10]:
            print(f"    drop n{d['n']}: {d['reason']}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", help="approved source name (see --list)")
    ap.add_argument(
        "--against",
        default="microban,pullban,autoban",
        help="comma list of corpora to dedup against (default: the built-ins)",
    )
    ap.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    ap.add_argument("--dry-run", action="store_true", help="fetch+parse+dedup, don't write/register")
    ap.add_argument("--list", action="store_true", help="print the approved-source allowlist and exit")
    args = ap.parse_args()
    if args.list or not args.corpus:
        print("Approved sources (license — author):")
        for name, s in APPROVED_SOURCES.items():
            print(f"  {name:12} {s['license_id']:36} {s['author']}  <{s.get('url') or s.get('url_template')}>")
        return
    ingest(
        args.corpus,
        against=tuple(a for a in args.against.split(",") if a),
        cache_dir=args.cache_dir,
        force=args.force,
        write=not args.dry_run,
    )


if __name__ == "__main__":
    main()
