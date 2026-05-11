---
node_id: resource::concorda::approval_request
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 044fdeee4ed2a4ad3e8d8402be3e34c15657135debc2d007f2254290c90726b8
---

# ApprovalRequest

## What it is

A row in the `approval_requests` table representing one pending
state transition that requires N-of-M sign-off. The generic engine
behind co-owner invites/promotions/removals, ownership transfers, and
similar workflows that can't be expressed as a single role check.

Each request has:
- A `request_type` (`boat_coowner_invite`, `boat_coowner_promotion`,
  `boat_coowner_removal`, `boat_ownership_transfer` — registered in
  `services/approval_types/`)
- A `subject_uuid` (the row being acted upon, e.g. a target BoatCrew)
- A `target_state` JSON (what the transition should produce on resolve)
- A set of `ApprovalVote` rows (one per voter; resolution rule per type:
  `unanimous`, `majority`, `first_responder`)
- A `status` (`pending`, `approved`, `rejected`, `expired`, `canceled`)

## Resolution

When the per-type resolution rule is satisfied (e.g. all voters approved
for `unanimous` types), `_finalize` fires the type-specific `on_approve`
or `on_reject` handler. Side effects include:
- Activating/cancelling a `BoatCrew` row
- Swapping the `owner` `BoatCrew` for ownership transfers
- Dispatching notifications to requester + remaining voters

## Co-owner eligibility check

The candidate `rule::coowner::eligibility_at_accept` enforces that a
`boat_coowner_invite` invitee must hold an active Boat Owner membership
(a PersonProduct with `grants_boat_management=True`) at vote time, not
at invite-send time.

## Relationships

- **Has many** `ApprovalVote` (one per voter, with decision +
  optional reason)
- **Subject of** the transition is keyed by `subject_uuid` (varies by
  request type — typically a `BoatCrew` row)
- **Requested by** a Person (`requested_by_uuid`)

## Technical anchor

- **Model**: `concorda-api/models/approval_request.py::ApprovalRequest`
- **Type registry**: `concorda-api/services/approval_types/`
- **Cast vote**: `concorda-api/services/approvals.py::cast_vote`
- **List endpoints**: `GET /api/approval-requests?voter=me|requester=me|subject_uuid=...`
