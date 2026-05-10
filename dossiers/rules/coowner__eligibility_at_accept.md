---
node_id: rule::coowner::eligibility_at_accept
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-10
last_reviewed_against_hash: 9aaed1960315afdaedb8172872c2069d6f36d6e5c43d61261deaf36c25e46e08
fan_out: 2
---

# Boat Owner membership is enforced at accept-time, not send-time

## The rule

When an existing boat owner invites someone to become a co-owner, the
recipient does **not** need to already have a Boat Owner membership
(the `boat_management` product grant). The send-side endpoint
deliberately accepts the invite without checking the recipient's
eligibility. The check fires later, at vote-time: when the invitee
votes "approved" on the underlying approval request, the system
verifies they have the grant. If they don't, the vote is rejected
with a clear upgrade prompt rather than silently failing.

## Why it exists

Before commit `4c7de14` (2026-05-07), the boats.py invite endpoint
required the recipient to already hold a Boat Owner membership.
Owners were getting blocked at invite-send time when their
collaborator hadn't upgraded yet. The recipient never even saw the
invite, and the inviter saw an opaque error.

Moving the check to accept-time fixes the UX:

- The invitee receives the invite (the approval-request notification).
- They see a co-owner invite is waiting and what boat it's for.
- When they try to accept and don't have the membership, they get a
  clear "you need a Boat Owner membership; upgrade under My Profile →
  Membership" message.
- They upgrade, then approve, and the co-ownership lands.

Send-time enforcement was hiding the upgrade path. Accept-time
enforcement surfaces it at the moment of decision.

## Examples

- **Bob (existing owner) invites Carol who has Member tier.** Invite
  succeeds; Carol gets the notification. Carol opens the invite and
  clicks Approve. The vote fails with HTTP 400: "A Boat Owner
  membership is required to accept this invite. Upgrade under My
  Profile → Membership and try again." Carol upgrades, re-approves,
  approval lands, Carol becomes co-owner.
- **Bob invites Dan who already has Boat Owner tier.** Invite
  succeeds; Dan approves directly; co-ownership lands without
  friction.
- **Bob invites someone with no Concorda account.** Different rule —
  the invite endpoint requires a person_uuid or known email; if no
  account exists, the endpoint returns 404 with "Ask them to sign up
  first." This rule kicks in only after they have an account.

## Counter-examples (what the rule does NOT do)

- The rule does **not** prevent the invite from being sent to an
  ineligible recipient. That was the whole point of the change —
  upfront blocking is what was removed.
- The rule does **not** check eligibility on the inviter (they're
  already a Boat Owner relationally; whether they have the
  membership product is checked elsewhere if at all).
- The rule does **not** apply to other approval types
  (`boat_coowner_promotion`, `boat_coowner_removal`,
  `boat_ownership_transfer`). Each has its own eligibility logic.
- The rule does **not** check at request-creation time inside
  approvals.py (`create_request`). It checks specifically on the
  vote-cast for an approved decision.

## Decision table

| Action                                              | request_type           | voter is invitee? | voter has boat_management? | Outcome                              |
|-----------------------------------------------------|------------------------|--------------------|----------------------------|---------------------------------------|
| Send invite                                         | (any)                  | n/a                | n/a                        | Always allowed (no eligibility check) |
| Other owner approves                                | boat_coowner_invite    | no                 | n/a                        | Vote recorded                         |
| Other owner rejects                                 | boat_coowner_invite    | no                 | n/a                        | Vote recorded; request resolves rejected |
| Invitee approves with grant                         | boat_coowner_invite    | yes                | yes                        | Vote recorded                         |
| **Invitee approves without grant**                  | **boat_coowner_invite**| **yes**            | **no**                     | **HTTP 400 — upgrade prompt; no vote recorded** |
| Invitee rejects                                     | boat_coowner_invite    | yes                | n/a                        | Vote recorded                         |
| Invitee approves on a non-coowner-invite request    | (other)                | yes                | n/a                        | Vote recorded (rule does not apply)   |

## Edge cases

- **Invitee approves, then their grant expires before all owners
  approve.** Currently no re-check; their vote stands. If this
  becomes a real concern, add a re-check at finalize-time.
- **Invitee was an active member when the invite was sent and is
  still active when they approve.** Standard happy path.
- **Owner-side rejection while invitee is upgrading.** The request
  could resolve rejected before the invitee gets a chance to upgrade
  and approve. Acceptable — owner intent is binding.
- **Invitee already an owner of this boat.** Caught earlier at
  invite-send time (`boats.py:834: "Already an owner"`). The
  approval flow won't be reached.

## Surfaces

- **Enforcer** (`enforces`,
  `concorda-api/services/approvals.py::cast_vote` at lines 93–103):
  the check itself. Inspects request_type, voter identity, and
  product grant; raises HTTP 400 with the upgrade prompt if the
  invitee lacks the grant.
- **Send-side acknowledgment** (`checks`,
  `POST /api/boats/{boat_id}/coowner-invite` at boats.py:829–831):
  the inline comment documents the deferral. The endpoint
  intentionally does not block.

The membership-grant predicate
`_has_boat_management(db, person_uuid)` lives in approvals.py at
line 21–31; it joins PersonProduct with TemporalProduct and returns
True if any active grant has `grants_boat_management=True`.

## Open questions

- Should there be a **send-time hint** (not block) telling the inviter
  that the recipient currently lacks the membership? Could appear in
  the invite-creation response as a non-blocking advisory. UX call.
- Should the **expiry check** at vote-finalize re-verify the grant?
  Currently no; first valid approval stands. Likely fine.
- The same accept-time-vs-send-time logic could plausibly apply to
  `boat_coowner_promotion` (promoting an existing crew member to
  co-owner). Currently the promotion path doesn't have an
  eligibility check at all. Worth designing.
