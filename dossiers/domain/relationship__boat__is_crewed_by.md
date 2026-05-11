---
node_id: relationship::boat::is_crewed_by
node_kind: domain
node_subkind: relationship
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: f1565d4bb4488e981b7323e8cf99bd1cb95781576faa58182d814047e4ea1cb6
---

# Boat is crewed by Person

## What it is

Crew membership of a Boat is a participation relationship: people who
sail on this Boat in one or more races. It is operationally distinct
from ownership (the structural authority).

In current code, crew lives in two places:

1. **Saved crew pools** — `boat_crew` rows with `role` values other
   than `owner` (e.g. `crew`, `alternate`), scoped to the boat. The
   captain's "regular crew."
2. **Per-race crew rosters** — `event_crew` rows scoped to a
   `sailing_event` (one boat at one event). This is the authoritative
   record of who actually crewed on a given race.

## Predicate

A Person P is crew on Boat B iff:
- (saved-pool sense) there's a `boat_crew` row with
  `boat_uuid = B`, `person_uuid = P`, `role != 'owner'`,
  `status = 'active'`. OR
- (per-race sense) there's an `event_crew` row with
  `sailing_event.boat_uuid = B`, `person_uuid = P`,
  `status in ('invited','accepted','confirmed')` for some event.

## Mediation

`boat_crew` (for saved pool) **and** `event_crew` (for per-race).

⚠ **Mediation collision**: the `boat_crew` table also mediates
`relationship::boat::is_owned_by`. Ownership and crew participation
share storage. They have different lifecycles (approval-gated vs.
casual invite-cycle), different cardinalities (1..many vs. 0..many),
and different semantics. The shared table is a category error; the
right shape is a dedicated `boat_ownership` table separate from
crew tables. See `rule::boat_ownership::via_boatcrew_not_owner_ids`.

## Cardinality

`0..many`. A boat can have zero crew (an owner sailing alone) or
many (a fully-rostered race). No upper bound enforced.

## Lifecycle

- **Saved-pool crew** are added/removed casually by the boat owner
  (no approval flow). They're a captain's address book of "people
  I might invite," not a binding membership.
- **Per-race crew** lifecycle on `event_crew.status`:
  `requested` → `invited` → `accepted` → `confirmed` → `attended`,
  with cancel/decline branches. Tied to the SailingEvent's lifecycle.

The two lifecycles are independent — a person can be in a captain's
saved pool but not invited to a given race, or invited to a race
without being in the saved pool.

## Examples

- **Saved pool**: Bob's boat has Carol, Dave, and Eve in the saved
  crew pool (`boat_crew` rows, `role='crew'`).
- **Race roster**: For the Wednesday Night Series race 4, Bob's
  SailingEvent has `event_crew` rows for Carol and Dave (Eve
  declined). Carol is "confirmed," Dave is "accepted."
- **Cross-boat crew**: Carol can be crew on Bob's boat AND on Alice's
  boat. Independent `boat_crew` / `event_crew` rows.

## Edge cases

- **An owner can also be "crew"** (in the saved-pool sense) of their
  own boat — but they'd be represented by their owner row, not a
  separate crew row. The shared-table model makes this awkward.
- **Crew finder vs. saved pool**: a Person published in the
  crewfinder is *not* automatically in any boat's saved pool. Pools
  are owner-curated, not self-asserted.

## Technical anchor

- **Saved pool query**: `boat_crew` with `role IN ('crew','alternate',
  ...)` and `status='active'`.
- **Per-race query**: join through `sailing_event` to `event_crew`.
- **Adjacent ontology**: `resource::concorda::event_crew`,
  `resource::concorda::sailing_event`.
- **Sibling relationship (collision)**: `relationship::boat::is_owned_by`.
