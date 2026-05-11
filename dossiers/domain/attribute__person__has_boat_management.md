---
node_id: attribute::person::has_boat_management
node_kind: domain
subkind: attribute
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 079c83fc387c16dd3611761101d3a7aaa3ac239da1e61a5e193994021416a235
---

# has_boat_management

## What it is

A derived boolean attribute on a Person: true iff they hold any active
`PersonProduct` row whose linked `TemporalProduct` has the
`grants_boat_management` flag set. In plain English: "does this person
hold a Boat Owner membership right now."

Computed dynamically — there is no cached column. Every check joins
`PersonProduct` to `TemporalProduct` at request time.

## Predicate

```sql
EXISTS (
  SELECT 1 FROM person_products pp
  JOIN temporal_products tp ON pp.product_id = tp.id
  WHERE pp.person_uuid = :person_id
    AND tp.grants_boat_management = True
)
```

## Why it matters

Two load-bearing gates depend on this attribute:

1. **Boat registration** — `POST /api/profile/boats` requires the
   caller to hold this entitlement (`_require_boat_management`).
   Free / crew-only members cannot register boats.
2. **Co-owner accept** — when an invitee votes `approved` on a
   `boat_coowner_invite` ApprovalRequest, `cast_vote` checks this
   attribute on the invitee. If false, the vote is rejected with a
   400 + upgrade-prompt copy. Per the candidate rule
   `rule::coowner::eligibility_at_accept` — enforced at accept time,
   not at invite-send time, so an owner can invite a non-member without
   the system blocking.

## Lifecycle

The attribute flips on when:
- A Person completes a paid membership purchase for a TemporalProduct
  with `grants_boat_management = True`.
- An admin grants them a PersonProduct manually.

It flips off when:
- The `PersonProduct` row is deleted (e.g. by `/membership/upgrade`'s
  delete-then-insert pattern, if the new membership doesn't grant
  boat management).
- All membership rows expire (though no expiration column exists
  today — flips off only on explicit delete).

## Technical anchor

- **Canonical helper**: `concorda-api/services/approvals.py::_has_boat_management`
- **Boat-registration gate**: `_require_boat_management` (similar
  helper)
- **Co-owner enforcement**: `concorda-api/services/approvals.py::cast_vote`,
  candidate rule `rule::coowner::eligibility_at_accept`
- **TemporalProduct flag**: `concorda-api/models/temporal_product.py::TemporalProduct.grants_boat_management`
