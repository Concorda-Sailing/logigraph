---
node_id: relationship::boat::is_owned_by
node_kind: domain
node_subkind: relationship
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 912c81102d698d151345b12b3a4139e18e540c5a6c257b9ccfcdea87975a13a5
---

# Boat is owned by Person

## What it is

Ownership of a Boat is the authority to register it for events, edit
its profile, invite crew, transfer it, and dissolve it. A Boat has
one or more owners; multiple owners are equal in authority. Ownership
is the **structural** property of a Boat, not a participation
relationship.

## Predicate

A Person P is an owner of Boat B iff there exists a row in
`boat_crew` with `boat_uuid = B`, `person_uuid = P`, `role = 'owner'`,
and `status = 'active'`.

## Mediation

Today: `boat_crew` table, filtered by `role='owner'` + `status='active'`.

⚠ **Mediation collision**: the same `boat_crew` table also mediates
`relationship::boat::is_crewed_by` (crew membership). Ownership and
crew participation are conceptually distinct — different lifecycles,
different cardinalities, different semantics — but they share storage.
See `relationship::boat::is_crewed_by` and the rule
`rule::boat_ownership::via_boatcrew_not_owner_ids` for the audit
finding. The category error is logged here so future migrations
(splitting BoatCrew → BoatOwnership + BoatCrew proper) have a
breadcrumb.

## Cardinality

`1..many`. Every Boat has at least one owner (no policy enforces
this, but it's the operational expectation). Multiple owners are
equal — the system has no concept of "primary" owner.

## Lifecycle

**Approval-gated.** Acquired and modified only through
`ApprovalRequest` flows of types:

- `boat_coowner_invite` — proposer invites someone to become a
  co-owner. Invitee votes; on approval, a new BoatCrew row is
  inserted with `role='owner'`.
- `boat_coowner_promotion` — promotes an existing crew member to
  owner. (Possibly legacy; see audit note on
  `rule::boat_ownership::via_boatcrew_not_owner_ids`.)
- `boat_coowner_removal` — removes an owner. Proposer + target both
  vote; on approval, the BoatCrew row's status changes.
- `boat_ownership_transfer` — moves ownership from one Person to
  another.

There is no path to acquire ownership outside the approval flow
(except the original `Boat.owner_ids` legacy column, which is
deprecated and must not be source-of-truth).

## Examples

- Bob registered "Wind Dancer." `boat_crew(boat=Wind Dancer,
  person=Bob, role='owner', status='active')` exists. Bob owns
  Wind Dancer.
- Carol accepts a co-owner invite. A new `boat_crew` row inserts
  with the same role/status. Both Bob and Carol now own Wind Dancer
  with equal authority.

## Edge cases

- **Orphan-boat possible**: there is no invariant that prevents the
  last owner from removing themselves via `coowner-remove`. A boat
  can land in "zero active owners" state. This is unresolved policy.
- **The hyphenated `co-owner` legacy `role` value**: if any
  `boat_crew` row still has `role='co-owner'` (with hyphen) in
  production, the canonical predicate `role='owner'` misses them.
  Verify and migrate.

## Technical anchor

- **Predicate code**: `concorda-api/services/approvals.py::_has_boat_management`
  for entitlement; `boat_crew` direct queries for ownership.
- **Approval dispatch**: `concorda-api/services/approvals.py` —
  request_type handlers.
- **Adjacent rule**: `rule::boat_ownership::via_boatcrew_not_owner_ids`.
- **Sibling relationship (collision)**: `relationship::boat::is_crewed_by`.
