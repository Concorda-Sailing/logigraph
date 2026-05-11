---
node_id: relationship::approval_request::has_voter
node_kind: domain
node_subkind: relationship
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 39dfcee868ca78c0f0f2637f9a908446d18ff0660f4da080a55bbc2790f92e19
---

# ApprovalRequest has voter Person

## What it is

An `ApprovalRequest` is decided by a fixed set of voters seeded when
the request is created. The voter set is determined by the
`request_type`'s `on_create` handler and is **immutable** after
creation — you cannot add or remove voters later.

## Predicate

Person P is a voter on ApprovalRequest R iff there exists an
`approval_vote` row with `request_id = R` and `voter_person_uuid = P`.

## Mediation

`approval_vote` table. The row is seeded with `vote = NULL` at
request creation and updated when the voter casts a decision.

## Cardinality

`1..many` voters per request. Each voter belongs to exactly one
request (no cross-request voter rows).

## Lifecycle

**Frozen at request creation.** The voter set is determined by the
`request_type`'s `on_create` handler:

- `boat_coowner_invite` — invitee is the sole voter.
- `boat_coowner_promotion` — all current owners.
- `boat_coowner_removal` — proposer + target.
- `boat_ownership_transfer` — proposer + target.

Voters can cast / change votes while the request is `pending`. Once
resolution fires (`approved`, `rejected`, `expired`, `canceled`),
votes can no longer change but the rows remain as history.

## Examples

- Bob invites Carol as co-owner. A `boat_coowner_invite` request is
  created; Carol is seeded as the sole voter. Bob is not a voter on
  his own invite.
- Carol files a removal request targeting Bob. Both Carol (proposer)
  and Bob (target) are voters.

## Edge cases

- **A request with no voters is invalid.** `on_create` must seed at
  least one — otherwise the resolution rule has nothing to decide on.
- **Changing the voter set requires canceling and re-issuing the
  request.** There's no in-flight amendment.

## Technical anchor

- **Voter seeding**: `concorda-api/services/approval_types/<type>.py`
  `on_create` hooks.
- **Vote endpoint**: `POST /api/approval-requests/{id}/vote`.
- **Resolution dispatch**: per type spec (`unanimous`, `majority`,
  `first_responder`).
- **Adjacent ontology**: `resource::concorda::approval_request`,
  `role::relational::approval_voter`.
