# Design spec: Pull as an earned ability + par-after-Pull (+ pull limits)

Status: **proposal, not yet built.** Captures the intended Pull-as-earned-ability direction
for a later round. No code changes accompany this doc. Build behind new
options and bump the world version when shipped (new options/items touch the datapackage —
see [VERSIONING.md](../VERSIONING.md)).

## Motivation

Today the **Pull** mechanic is a binary: it's either always available, or (with
`expert_logic` + a pull-required corpus like `pullban`) hard-gated behind a single Pull
item that unlocks the pull-required levels. On the default Microban corpus — which is 100%
push-solvable — Pull is irrelevant and the button is hidden. We want Pull to feel like an
*earned ability* that matters even on push-only content, without making base levels
unsolvable (which would break the "generator never solves Sokoban" guarantee — solvability
stays push-only and precomputed).

Three linked ideas, in increasing scope:

1. **Pull shouldn't always be available.** Make Pull a gated progression item more broadly.
2. **Par-after-Pull on push-only levels.** A level's *par* check (the optional "solve in ≤
   par pushes" location) is only in-logic once Pull is received — so Pull gates the
   *mastery/par* tier even on levels that are solvable without it.
3. **Per-level pull limit (sketch).** On gated levels, cap how many pulls you may use.

## Current state (what exists today)

- **Options** (`apworld/sokopelago/Options.py`): `ParChecks` (Toggle, default off),
  `PullLogic` (Toggle, default off — renamed from `ExpertLogic` in 0.6.0). Par locations are
  added per level when `par_checks` is on; they're marked `LocationProgressType.EXCLUDED`
  (filler-only, can't hold progression), so a hard par requirement can never soft-lock a seed.
- **Pull gating** (`apworld/sokopelago/__init__.py`): `self.pull_levels` is non-empty only
  when `pull_logic` is on AND the corpus has `requires_pull` levels. `_apply_pull_gate(loc,
  n)` sets `loc.access_rule = lambda s: s.has(PULL_NAME, p)` on both the solve and par
  locations of a pull-required level. Exactly one `Pull` progression item is created.
- **slot_data**: `pull_logic: bool`, `requires_pull: {levelStr: true}` (only gated
  levels), `par_checks: bool`, `par: {levelStr: pushCount}`.
- **Client** (`client/src/ap/session.ts`): `canPull = !pull_logic || pullReceived`;
  `needsPull(n) = pull_logic && requiresPull(slot, n)`. Par is reported in `reportSolved`
  when `pushCount <= par`. There is **no per-level pull counter** — only `game.pushes`.
- **Shipped (this round):** Pull is now **solo-only god-mode** — always usable in solo free
  play (`dev.sh`), but in AP it's gated to pull-capable/expert seeds (`main.ts pullInSeed`/
  `canPullNow`), so `Shift+arrow` no longer pulls on a vanilla Microban AP seed. Full AP
  gating (Options A/B below) is not yet implemented.

## Proposed design

### Option A — Pull gates par on push-only levels (the core idea)

New option, e.g. **`pull_gates_par`** (Toggle, default off; only meaningful with
`par_checks` on). When on:

- Every level's **par location** gets the Pull access rule (reuse the existing
  `_apply_pull_gate` pattern), regardless of whether the level is pull-*required*. The
  **solve** location stays ungated, so base progression never depends on Pull.
- Implies a `Pull` item exists in the pool even on a push-only corpus. Today the Pull item
  is created only when `self.pull_levels` is non-empty; extend that condition to also fire
  when `pull_gates_par` is on.
- slot_data: add `pull_gates_par: bool`. The client's "can I claim par?" check becomes
  `par_checks && (!pull_gates_par || pullReceived)`.

Result: you can *solve* every level from the start, but *par* (the mastery tier) only counts
once you've found Pull — making Pull a meaningful, universally-relevant progression item.
Because par locations are `EXCLUDED`, fill can still never strand progression behind Pull.

Touch points:
- `apworld/sokopelago/Options.py` — new `PullGatesPar` toggle.
- `apworld/sokopelago/__init__.py` — broaden the Pull-item condition; in `create_regions`
  apply the pull gate to *par* locations when `pull_gates_par` (independent of
  `pull_levels`); add `pull_gates_par` to `fill_slot_data`.
- `client/src/ap/slotData.ts` + `session.ts` — new field; gate par reporting/UI on Pull.
- `client/src/main.ts` — surface "par needs Pull" in the selector/par note; only let Pull
  mode help toward par once Pull is owned.

### Option B — Pull as a more general gated item

Decide the default posture for Pull availability. Options:
- Keep Pull ungated unless an expert/par-gating option is on (status quo + Option A). Lowest
  risk; recommended default.
- Add an explicit **`pull_ability`** choice (e.g. `always | earned`) so a seed can require
  finding Pull before the mechanic works at all, independent of expert/pullban. If `earned`,
  the client hides/disables Pull until the item arrives (the `canPull` plumbing already
  exists).

### Option C — Per-level pull limit (sketch, lowest priority)

Cap pulls on gated levels (e.g. "par here allows ≤ K pulls"). Open questions:
- Where does the limit come from? A global option, or per-level data computed offline by
  the solver (`tools/solve_corpus.py`)?
- Client needs a **pull counter** (new; today only `game.pushes` is tracked). Add
  `game.pulls` to `client/src/board.ts` and surface remaining pulls in the HUD; block the
  par check (or the pull action) once the budget is spent.
- slot_data: `pull_limit: {levelStr: K}` (or a single global int).
- Interaction with Undo: does undoing a pull refund the budget? (Probably yes — track via
  the existing `history`/`MoveRecord`.)

Recommend deferring C until A is in and playtested; it adds the most surface area
(per-level data, a new counter, HUD, undo semantics).

## Datapackage / versioning notes

- New **options** are backward-compatible defaults-off, but any new **item** (e.g. forcing a
  Pull item into push-only seeds) or **location** changes the datapackage → **minor** bump
  (`0.x → 0.(x+1)`) and a CHANGELOG entry when built.
- Keep solvability push-only and precomputed (ROADMAP hard constraint): Pull gating only
  ever affects *optional* (par) checks or *expert* levels, never base solve-reachability.

## Terminology: "expert" was a misnomer — renamed to `pull_logic` (DONE in 0.6.0)

The old `expert_logic` / "expert ability-logic tier" conflated two unrelated things: **using
the Pull mechanic** and **being hard**. A pull-required level isn't inherently harder to
*solve* than a tricky push-only one — it just needs a different verb. **Shipped in 0.6.0:**
the option/tier was renamed to `pull_logic` / "Pull Logic" to name the mechanic, not a
difficulty claim. This was a **breaking** option/slot_data rename (old yamls used
`expert_logic`; no alias — AP ignores the unknown key). Touch points covered: option key in
`Options.py`, the `fill_slot_data` key, `slotData.ts`, and `session.ts`/`main.ts`
(`pull_logic` reads + the `pullInSeed`/`canPull` logic).

Separately, **difficulty** (the `◆◇◇` pips) currently comes from the solver's normalized
score. A naive **par-based** difficulty (more pushes ⇒ harder) was floated — cheap, and
"probably good enough" — but it mismeasures cases like a long trivial corridor (many pushes,
no thinking). If we revisit difficulty, consider blending par with the solver's branching/
search metric rather than par alone. Low priority; the current solver score is fine.

## Recommended sequencing

1. **Option A** (`pull_gates_par`) — highest value, reuses `_apply_pull_gate`, can't
   soft-lock (par is EXCLUDED).
2. **Option B** `pull_ability: earned` if we want Pull gated outside expert seeds.
3. **Option C** per-level pull limits — only after A/B land and playtest well.
