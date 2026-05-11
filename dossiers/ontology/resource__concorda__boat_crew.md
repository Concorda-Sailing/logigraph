---
node_id: resource::concorda::boat_crew
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 58cf8e8050780e1aa027f6259878b12a929d4af2e146d90bdde2cd07b18de5f1
---

# BoatCrew

## What it is

A row in the `boat_crew` table representing one (`boat`, `person`)
relationship. `role` distinguishes `owner` from `crew`; `status` carries
the lifecycle (`active`, `invited`, `declined`, `prospective`, `removed`).
Every boat-related authority decision routes through this table: who
owns the boat, who can edit it, who is on its crew roster, who has
accepted vs. declined an invite.

Distinct from `EventCrew` — that's the per-event slot; this is the
boat-level relationship.

## Key fields

- `boat_uuid`, `person_uuid` — the (boat, person) pair. Indexed; logically
  unique-per-pair but no DB constraint enforces it.
- `role` — `owner` or `crew` (free string in DB).
- `status` — `active`, `invited`, `declined`, `prospective`, `removed`.
- `position` — optional preferred position (e.g. "Trim").
- `priority` — integer ordering within the boat's crew; click-order =
  priority 1 (see `project_invite_priority_order`).
- `invited_by_uuid` — who issued the invite.
- `notes` — owner-side notes.

## Lifecycle (crew row)

```
invited ──accept──► active
        └─decline─► declined  (re-invite is allowed; previous row replaced)

prospective ──owner promotes──► invited
            └──owner declines──► (row deleted)
```

## Lifecycle (owner row)

```
(seeded at boat creation) ──► active
                          └─► via Approval(coowner_invite_accept) ──► another active row
                          └─► via Approval(coowner_removal_complete) ──► (row deleted)
```

## Relationships

- **References** `Boat` via `boat_uuid`
- **References** `Person` via `person_uuid`
- **References** `Person` via `invited_by_uuid` (the inviter)
- **Sibling to** `PendingCrewInvite` (email-only invites where the
  recipient doesn't yet have a Person row — converts to BoatCrew on
  signup)

## Visibility

- Owners always see all rows for their boats, unfiltered.
- Peer crew see other rows on the same boat, with PII gated by
  `rule::crew_visibility::peer_pii_resume_gated`.

## Technical anchor

- **Model**: `concorda-api/models/boat_crew.py::BoatCrew`
- **Read schema**: `concorda-api/schemas/boat.py::BoatCrewRead`
- **Owner predicate**: `role='owner' AND status='active'`
  (see `role::relational::boat_owner`).
- **Owner-gate helper**: `concorda-api/routers/boats.py::_require_owner`.
- **Co-owner promotion / removal**: handled via the `ApprovalRequest`
  system (`boat_coowner_invite`, `boat_coowner_promotion`,
  `boat_coowner_removal` request types).
