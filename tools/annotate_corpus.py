#!/usr/bin/env python3
"""Annotate a corpus: solve (capped, parallel) where needed + score, writing the scoring
module's features into the manifest as **new additive fields**.

This is the offline annotator for the curated dataset. For each level it assembles a
``solve_corpus.solve`` result and runs ``scoring.compute_features`` on it, then merges the
features into ``apworld/sokopelago/data/<corpus>.json`` alongside the existing fields (the
``build_corpus.merge_boards`` preserve pattern: existing solver fields are never overwritten,
``n``/``name``/``board`` are refreshed, the new feature fields are added).

Two non-negotiables baked in here:

* **One shared absolute difficulty scale.** Every corpus is normalized against *Microban's*
  native reference bounds (``solve_corpus.reference_bounds``), so a ``difficulty`` of 0.5 means
  the same thing in every set and the absolute ``EASY_MAX``/``HARD_MIN`` tier cutoffs stay
  meaningful across corpora. A set genuinely harder than Microban clamps toward 1.0 (reported).
* **Non-destructive.** A level that already carries an authoritative solution (e.g. the shipped
  Microban manifest, solved by the full coverage ladder) is *not* re-solved — its base fields are
  reused as-is so the capped solve here can never downgrade them. Only levels lacking a solution
  (a freshly-ingested set) are solved, capped and parallel, mirroring ``generate_corpus``.

Run:  python tools/annotate_corpus.py --corpus microban2 [--workers 8] [--node-budget 2000000]
      python tools/annotate_corpus.py --corpus microban --dry-run   # smoke test, no write
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import time
from time import monotonic

import provenance
import scoring
import solve_corpus
from generate_corpus import _apply_scoring_caps  # reuse the deterministic single-phase cap
from xsb_levels import REPO_ROOT, corpus_xsb, load_corpus, manifest_json, parse_levels

# Solver/base fields copied from a *fresh* solve into the manifest (existing ones are preserved).
_BASE_KEYS = ("par", "moves", "solution", "boxes", "search_nodes", "difficulty", "optimal", "solved", "solver")


def microban_reference_bounds():
    """The single shared scale: Microban's native difficulty bounds (see module docstring)."""
    ref = json.loads(manifest_json("microban").read_text(encoding="utf-8"))
    return solve_corpus.reference_bounds(ref)


def _annotate_one(rows, existing: dict, ref_bounds) -> dict:
    """Solve (only if needed) + score one level. ``rows`` is the raw XSB board; ``existing`` is
    its prior manifest entry (possibly empty). Returns the merge payload for the main process."""
    level = parse_levels("; 1\n\n" + "\n".join(rows))[0]
    if existing.get("solved") and existing.get("solution"):
        result = existing  # authoritative — reuse, never re-solve/downgrade
        base: dict = {}
    else:
        entry = solve_corpus.solve(level)
        solve_corpus._attach_difficulty([entry], ref_bounds=ref_bounds)  # shared Microban scale
        result = entry
        base = {k: entry[k] for k in _BASE_KEYS if k in entry}
    features = scoring.compute_features(level, result)
    return {"base": base, "features": features, "solved": bool(result.get("solved"))}


def _worker(rows, existing, node_budget, ref_bounds, out: "mp.Queue") -> None:
    try:
        _apply_scoring_caps(node_budget)
        out.put(_annotate_one(rows, existing, ref_bounds))
    except Exception:  # a malformed level must never crash the run
        out.put(None)


def parallel_annotate(items, workers: int, node_budget: int, wall_cap: float, ref_bounds):
    """Annotate ``items`` (``(rows, existing)`` pairs) concurrently, results in input order.
    The node budget bounds each (capped) solve; ``wall_cap`` is a per-level kill backstop.
    ``workers<=1`` runs in-process (deterministic; used by tests and the Microban smoke test)."""
    n = len(items)
    results: list[dict | None] = [None] * n
    if n == 0:
        return results
    if workers <= 1:
        _apply_scoring_caps(node_budget)
        for i, (rows, existing) in enumerate(items):
            try:
                results[i] = _annotate_one(rows, existing, ref_bounds)
            except Exception:
                results[i] = None
        return results

    ctx = mp.get_context("fork" if hasattr(os, "fork") else "spawn")
    running: dict[int, tuple] = {}
    nxt = 0
    completed = 0
    while completed < n:
        while len(running) < workers and nxt < n:
            q: mp.Queue = ctx.Queue()
            rows, existing = items[nxt]
            p = ctx.Process(target=_worker, args=(rows, existing, node_budget, ref_bounds, q))
            p.start()
            running[nxt] = (p, q, monotonic())
            nxt += 1
        done: list[int] = []
        for i, (p, q, t0) in running.items():
            try:
                results[i] = q.get_nowait()
                p.join(timeout=1)
                done.append(i)
            except queue.Empty:
                if monotonic() - t0 > wall_cap:
                    p.terminate()
                    p.join(timeout=1)
                    results[i] = None
                    done.append(i)
        for i in done:
            del running[i]
            completed += 1
        if not done:
            time.sleep(0.005)
    return results


def annotate(name: str, *, node_budget: int = 2_000_000, wall_cap: float = 120.0,
             workers: int = 1, write: bool = True) -> tuple[list[dict], dict]:
    """Annotate corpus ``name`` and (optionally) write its manifest. Returns (entries, stats)."""
    prov = provenance.require(name)  # gate: no annotation without a recorded, redistributable source
    levels = load_corpus(corpus_xsb(name))
    out = manifest_json(name)
    existing = {}
    if out.exists():
        existing = {e["n"]: e for e in json.loads(out.read_text(encoding="utf-8"))}
    ref_bounds = microban_reference_bounds()

    items = [(list(lvl.rows), existing.get(lvl.n, {})) for lvl in levels]
    annotated = parallel_annotate(items, workers, node_budget, wall_cap, ref_bounds)

    entries: list[dict] = []
    solved_fresh = unsolved = reused = 0
    for lvl, ann in zip(levels, annotated):
        if ann is None:  # worker crashed/timed out -> mark unsolved, still emit a complete entry
            ann = {"base": {"solved": False, "boxes": len(lvl.boxes), "difficulty": 1.0},
                   "features": scoring.compute_features(lvl, {"solved": False, "boxes": len(lvl.boxes)})}
        merged = dict(existing.get(lvl.n, {}))
        merged.update(ann["base"])  # fresh base fields (empty when an authoritative one was reused)
        merged["n"], merged["name"], merged["board"] = lvl.n, lvl.name, list(lvl.rows)
        merged.update(ann["features"])
        merged["provenance"] = name
        merged["license"] = prov["license_id"]
        entries.append(merged)
        if not ann["base"]:
            reused += 1
        elif merged.get("solved"):
            solved_fresh += 1
        else:
            unsolved += 1

    stats = {"levels": len(entries), "reused": reused, "solved_fresh": solved_fresh,
             "unsolved": unsolved, "node_budget": node_budget}
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"annotated {len(entries)} levels -> {out.relative_to(REPO_ROOT)}")
    print(f"  reused={reused} solved_fresh={solved_fresh} unsolved={unsolved}")
    return entries, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Annotate a corpus with scoring features (additive).")
    ap.add_argument("--corpus", required=True, help="corpus name (must have a provenance entry)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--node-budget", type=int, default=2_000_000, help="per-level solve cap")
    ap.add_argument("--wall-cap", type=float, default=120.0, help="per-level kill-on-timeout (s)")
    ap.add_argument("--dry-run", action="store_true", help="compute but do not write the manifest")
    args = ap.parse_args()
    annotate(args.corpus, node_budget=args.node_budget, wall_cap=args.wall_cap,
             workers=args.workers, write=not args.dry_run)


if __name__ == "__main__":
    main()
