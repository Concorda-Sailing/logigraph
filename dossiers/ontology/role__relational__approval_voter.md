---
node_id: role::relational::approval_voter
node_kind: ontology
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 136d01f6eeb951d1cad9e5bdeca948bc3422c72df1cab8749ffaefff0a40af1e
---

# Approval Voter

## Plain definition

An Approval Voter is a Person seeded as a voter on a specific
`ApprovalRequest`. The voter set is determined by the request's
`request_type` at creation time (registered in
`services/approval_types/`) and is fixed thereafter — you cannot add
or remove voters after the request exists.

The voter set varies by request kind:
- **`boat_coowner_invite`** — the invitee is the sole voter.
- **`boat_coowner_promotion`** — all current owners (including the
  proposer) are voters; unanimous approval required.
- **`boat_coowner_removal`** — the proposer and the target are
  voters; mutual consent (both `approved`) required.
- **`boat_ownership_transfer`** — the proposer and the target are
  voters; both must approve.

## They can

- Cast a vote of `approved` or `rejected` on the request (`POST
  /api/approval-requests/{id}/vote`).
- Provide a `reason` string with their vote.
- Change their vote until the request finalizes (subject to the
  per-type rules).

## They cannot

- Vote on requests they aren't seeded on (403).
- Vote after the request has resolved (request is in
  `approved`/`rejected`/`expired`/`canceled` state).
- Vote on someone else's behalf.

## Becomes one when

- A `request_type`'s `on_create` handler seeds them as a voter when
  the `ApprovalRequest` is created.

## Stops being one when

- The request resolves (`approved`, `rejected`, `expired`, `canceled`).
  Past resolution, the voter row remains in history but new votes are
  rejected.

## Examples

- **Bob invites Carol as co-owner of Wind Dancer.** A `boat_coowner_invite`
  request is created; Carol is seeded as the sole voter. When Carol
  votes `approved`, the request finalizes (subject to her holding
  Boat Owner membership — see `rule::coowner::eligibility_at_accept`).
- **Carol files a co-owner removal request targeting Bob.** A
  `boat_coowner_removal` request is created; both Carol (proposer)
  and Bob (target) are seeded as voters. Both must vote `approved` for
  the removal to take effect.

## Distinctions

- **Approval Voter is not the same as ApprovalRequester.** The
  requester filed the request; voters are the people who decide its
  fate. They may or may not overlap (in `boat_coowner_invite`, they
  do not — the requester is an owner, the voter is the invitee).
- **Approval Voter is scoped to one request.** Being a voter on
  request R does not make someone a voter on request R'.

## Technical anchor

- **Predicate**: `ApprovalVote(request_id=R, voter_person_uuid=P)` row
  exists with the request still in `pending` status.
- **Vote endpoint**: `POST /api/approval-requests/{id}/vote`
- **Type registry**: `concorda-api/services/approval_types/` — each
  type's `on_create` decides the voter set.
- **Resolution rule**: `unanimous` (default), `majority`, or
  `first_responder`, per type spec.
