---
node_id: role::relational::boat_owner
node_kind: ontology
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-09
last_reviewed_against_hash: 9adde5c61387cca193ca36c3de9d07064deb3160c2c015b9b3a9210b597bf114
---

# Boat Owner

## Plain definition

A Boat Owner is the person whose boat it is. They became an owner by
registering the boat in Concorda, or by being promoted to co-owner via
an existing owner's request. A single boat can have multiple owners,
and all owners have **equal authority** — there is no senior or primary
owner once a co-ownership exists.

A "Boat Owner" is a *relational* role, not a system role. It's not
stored as a `UserRole` row. Membership is computed by joining the
person against the `BoatCrew` table for a specific boat: a person is a
Boat Owner of boat B iff there exists a `BoatCrew` row with
`person_id = them, boat_id = B, role = 'owner', status = 'active'`.

A person can be a Boat Owner of one boat and not another. The role is
always scoped to a specific boat.

## They can

- Invite people to be crew on their boat (existing members and
  non-members).
- Accept or decline crew requests for races their boat is in.
- Promote a crew member to co-owner — but only with **unanimous
  approval** from all current owners.
- Remove a co-owner — but only with **mutual consent** between the
  proposer and the target.
- See the unfiltered crew roster of their boat (PII not gated by the
  resume-publication rule).
- Edit the boat's profile, sail number, photos, and class.
- Generate share tokens for boat onboarding flows.
- Reorder the boat's crew priority.

## They cannot

- See unrelated boats' crew rosters or private metadata.
- Unilaterally remove another owner — that requires the target's
  consent.
- Bypass the co-owner promotion approval — even a sole owner can't
  add a co-owner without an explicit `Approval` flow record.
- Be removed as the only remaining owner (the boat becomes
  ownerless on deletion, not by removal).

## Becomes one when

- They register a new boat in Concorda (becomes sole owner of that
  boat at registration time).
- An existing owner files a co-owner promotion request for them, all
  current owners vote `approved`, and the request resolves. The
  promotion writes `BoatCrew.role = 'owner'` for the target.
- The system seeds a boat with an owner during data import (rare;
  treated as historical).

## Stops being one when

- All current owners (including themselves) vote `approved` on a
  co-owner removal request targeting them, and the request resolves.
- The boat is deleted (no rows remain; ownership is implicitly
  terminated).

## Examples

- **Bob registers "Wind Dancer."** Bob is the sole Boat Owner of Wind
  Dancer. He can invite Carol as crew, accept crew requests for
  upcoming races, and see all PII of his crew regardless of resume
  status.
- **Bob promotes Carol to co-owner of Wind Dancer.** Bob files a
  promotion request; he is the only current owner so his single
  approval satisfies "unanimous." Carol is now also a Boat Owner of
  Wind Dancer. Bob and Carol have equal authority — Carol can invite
  crew, edit the boat, etc., on her own.
- **Carol wants to remove Bob.** She files a removal request. The
  voters are Bob and Carol (current owners), and the rule is mutual
  consent: both must vote approved. Bob does not have to consent —
  if he votes rejected, the request fails and Bob remains an owner.

## Distinctions

- **Boat Owner is not the same as a Crew Member with admin-shaped
  permissions.** Crew members can have many capabilities (depending
  on `BoatCrew.status` and any custom delegations) but they are
  non-authoritative on ownership decisions. Only owners vote on
  promotion / removal approvals.
- **Boat Owner is scoped to a single boat.** Bob is an owner of
  Wind Dancer; he is not automatically anything-special on other
  boats just because he owns one.
- **Boat Owner is not the system role `org_admin` or
  `system_admin`.** Those are organization-wide system roles. Boat
  ownership is a relationship to a specific boat.
- **A "Co-owner" is a Boat Owner.** The terms are used
  interchangeably once a boat has more than one owner; both rows
  are `BoatCrew.role = 'owner'`. There is no senior/junior
  distinction in the data model.

## Technical anchor

- **Predicate**: `BoatCrew.role = 'owner' AND BoatCrew.status = 'active'`
- **Defined in**: `concorda-api/models/boat_crew.py`
- **Enforced by (canonical helper)**: `concorda-api/routers/boats.py::_require_owner`
  (lines 63–73) — the chokepoint used by 25+ boat-admin endpoints.
- **Frontend dispatch (correct pattern)**:
  `concorda-web/src/components/boat/boat-page.tsx` chooses
  `<BoatOwnerView>` vs `<BoatCrewView>` at the page boundary based on
  `mine.role === "owner"`. Role-based components, per the
  feedback in `feedback_role_based_components`.
- **Approval workflows**: co-owner promotion and removal both go
  through the `Approval` system; rules require unanimous-approval
  (promotion) and mutual-consent (removal).
- **Related rules**: see `_index/by_ontology.json` for the up-to-date
  list of rules that reference this node.
