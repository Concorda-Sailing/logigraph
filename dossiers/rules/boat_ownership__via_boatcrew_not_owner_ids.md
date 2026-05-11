---
node_id: rule::boat_ownership::via_boatcrew_not_owner_ids
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 8cacc1b4fa640078298942f35084564c11996604af2b241d0b748b6add0d1d28
fan_out: 7
---

# Boat ownership lives on BoatCrew, not Boat.owner_ids

## The rule

A Person is a Boat Owner of a Boat B iff there exists a row in the
`BoatCrew` table where `boat_uuid = B`, `person_uuid = P`,
`role = 'owner'`, and `status = 'active'`. This is the *only* source
of truth for boat ownership in current code.

The legacy `Boat.owner_ids` JSON column on the Boat row is kept for
backwards compatibility with old data but **must not** be read,
written, or compared by new code. It will drift, and queries that
join on it will be wrong.

Multiple owners are equal: a co-owner promoted via the approval
system has the same authority over the boat as the original owner —
edit rights, invite rights, transfer rights, the ability to register
the boat for events, all of it.

## Why it exists

Boats are owned. Boats are also shared — a husband and wife jointly
race a boat, a syndicate of four crew co-owns a boat, a sailing
program owns a fleet with multiple instructors. The early model
(`Boat.owner_ids` as a JSON list on the Boat row) couldn't carry the
audit trail of *how* each person became an owner, couldn't carry an
active/inactive flag, and couldn't be cleanly joined.

The current model — `BoatCrew` with `role` enumerating `owner`,
`co-owner` (legacy), `crew`, etc. and `status` enumerating `active`,
`pending`, `removed` — is normalized, joinable, and lifecycle-aware.
Co-owner promotion goes through `ApprovalRequest` (request_types
`boat_coowner_invite`, `boat_coowner_promotion`, `boat_coowner_removal`,
`boat_ownership_transfer`) which seeds voters per type, finalizes per
type-specific resolution rules, and on approval mutates the BoatCrew
row (flipping `role` or `status`).

The mistake the rule prevents: reading `boat.owner_ids` in a query,
finding it stale or empty, and concluding the boat has no owners
when the BoatCrew table says otherwise. Or writing to `owner_ids` to
record an ownership change and skipping the BoatCrew row that the
rest of the system relies on.

## Examples

- **Bob registered "Wind Dancer."** `BoatCrew(boat=Wind Dancer,
  person=Bob, role='owner', status='active')` exists. Bob is the
  Boat Owner.
- **Bob invites Carol as co-owner.** An `ApprovalRequest(type=
  'boat_coowner_invite')` is created. Carol votes `approved`. On
  finalization, a new `BoatCrew(boat=Wind Dancer, person=Carol,
  role='owner', status='active')` row is inserted. Carol is now
  also a Boat Owner; Bob still is too. Both have equal authority.
- **Carol later removes Bob via `boat_coowner_removal`.** Both vote
  approved. Bob's BoatCrew row is updated to `status='removed'` (or
  similar). Bob is no longer a Boat Owner; queries that join on
  `role='owner' AND status='active'` correctly exclude him.
- **Ownership transfer.** A `boat_ownership_transfer` ApprovalRequest
  moves the owner role from one Person to another; mid-transfer the
  source's BoatCrew goes inactive and the target's becomes
  `role='owner', status='active'`.

## Counter-examples (what the rule does NOT do)

- The rule does **not** forbid reading `Boat.owner_ids` *for
  diagnostic purposes* (e.g. detecting drift between the legacy
  column and the BoatCrew table). It forbids using it as
  source-of-truth.
- The rule does **not** say "anyone in BoatCrew is an owner." Only
  rows with `role='owner' AND status='active'` qualify. Crew rows
  (`role='crew'`, `role='alternate'`, etc.) are not owners.
- The rule does **not** apply to historical reporting where a
  point-in-time ownership snapshot is wanted. Use `BoatCrew` with
  date filters; the live query is what the rule covers.

## Decision table

| Predicate                                            | Outcome    |
|------------------------------------------------------|------------|
| `BoatCrew(boat=B, person=P, role='owner', status='active')` exists | P is an owner of B |
| `BoatCrew(boat=B, person=P, role='owner', status='removed')` only   | P is not currently an owner |
| `Boat.owner_ids` contains P, BoatCrew has no active owner row for P  | Data drift — **do not trust owner_ids** |
| `BoatCrew(boat=B, person=P, role='crew', status='active')`           | P is crew, not owner |
| Multiple `BoatCrew(role='owner', status='active')` rows for B        | All those persons are equal owners |

Ownership operations on a boat resolve the owning set by querying
BoatCrew, never by reading `owner_ids`.

## Surfaces

- **Mutation paths** (where a BoatCrew row's `role` or `status`
  changes):
  - `POST /api/invite/{token}/accept` — coowner-invite accept flips
    the pending row to `role='owner'`. Canonical mutation site.
  - ApprovalRequest finalization in `services/approvals.py` for the
    four boat_coowner_* types.
- **Ownership-gated endpoints** (must join through BoatCrew):
  - `PUT /api/profile/boats/{boat_id}` — only owners can edit.
  - `DELETE /api/profile/boats/{boat_id}` — only owners can delete.
  - `POST /api/profile/boats/{boat_id}/transfer` — only owners initiate.
  - `POST /api/boats/{boat_id}/coowner-invite` — only owners send
    invites.
  - `POST /api/boats/{boat_id}/coowner-remove` — only owners initiate.
- **Visibility decisions**:
  - `GET /api/boats/{boat_id}/crew/visible` — owners see unfiltered
    crew; the gate joins on BoatCrew.
  - `routers/boatfinder.py::_get_boat_owner` — picks "the first
    active owner" for display purposes (defensible because all
    active owners are equal).

## Gotchas

- **Co-owner-membership eligibility is checked at *accept time*, not
  invite time** (see `rule::coowner::eligibility_at_accept`). An
  owner can send an invite to a non-member; the system blocks the
  accept if the invitee doesn't hold a Boat-Management entitlement.
- **A single owner deleting themselves can orphan a boat.** There is
  no policy yet that prevents the last owner from removing themselves
  via `coowner-remove`. If you write code that assumes a boat always
  has at least one owner, that invariant is not enforced.
- **The "first active owner" pattern in boatfinder is a UI
  shortcut**, not a privilege grant. All co-owners are equal even if
  the UI displays only one.
- **Don't migrate code by writing to both `owner_ids` and
  `BoatCrew`.** Pick BoatCrew. Letting `owner_ids` linger as a
  written column re-introduces drift.

## Technical anchor

- **Canonical query** (Python): `select(BoatCrew).where(BoatCrew.boat_uuid == boat_id, BoatCrew.role == "owner", BoatCrew.status == "active")`
- **Approval flow**: `concorda-api/services/approvals.py` —
  `request_type` dispatch tables for `boat_coowner_invite`,
  `boat_coowner_promotion`, `boat_coowner_removal`,
  `boat_ownership_transfer`.
- **Models**: `concorda-api/models/boat_crew.py::BoatCrew`,
  `concorda-api/models/boat.py::Boat`.
- **Adjacent ontology**: `role::relational::boat_owner`,
  `resource::concorda::boat`, `resource::concorda::boat_crew`,
  `resource::concorda::approval_request`.
- **Adjacent rule**: `rule::coowner::eligibility_at_accept` (entitlement
  check at vote time — different concern, same area).
