# Design notes: escape valves (Skip / Undo / Hint) + a Panic button

Status: existing valves are shipped; the **Panic button** below is a **proposal**, not built.

## Shipped today

- **Skip Token** — consume one to clear a level you can't solve; sends its location check
  and advances. Token-gated (count set by the `skip_tokens` yaml option).
- **Undo Charge** — "smart undo": one press rewinds the trailing walk steps and your last
  push/pull (one charge); walk-only undos are free. (`undo_charges`.)
- **Hint Token** — animates the optimal line up to the next push; the first push is free,
  each further push costs a token. (`hint_tokens`.)

## Proposal: a Panic button (honor-system "get out of jail free")

Motivation: in a multiworld, a player hard-stuck on a level can hold up everyone waiting on
the items behind their checks. A **Panic** button would let a stuck player get unstuck for
**free** (no token), on the honor system, so they don't block the room.

Open questions to settle before building:
- **What does it do?** Options: (a) same as Skip but free (send the level's check and
  advance — "I give up, take the check"); (b) just unlock-advance to the next level without
  sending the check (forfeit the check, don't block others); (c) an AP `!release`-style
  forfeit of *all* remaining checks (nuclear, ends your run but unblocks everyone).
- **Abuse / honor system.** Free + sends checks = trivially beat the seed. So if it sends
  checks it probably should be rate-limited or logged; if it only forfeits/releases, abuse
  isn't a concern. Leaning toward (b)/(c): Panic forfeits, it doesn't reward.
- **Relationship to Skip.** Skip (token-gated) already "clears a level you can't solve." If
  Panic sends checks too, it's just a free Skip — maybe better to make Panic the *release*
  semantics (c) and keep Skip as the token-gated "credit me the check" valve.
- **Opt-in?** Likely a yaml toggle (`panic_button`, default on?) and/or always available as
  a client affordance independent of the seed.

Recommendation: prototype as **(b) free unlock-advance that forfeits the check** (or wire to
AP `!release` for (c)), so it can never be used to cheaply complete a seed. Build after the
Pull/par work.
