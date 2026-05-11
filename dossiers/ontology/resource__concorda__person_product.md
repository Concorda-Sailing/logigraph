---
node_id: resource::concorda::person_product
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 5b74cce6caa7f80fba9f08fa5f7d4cc86bef470e2f05b4a0b28bbf31715317c4
---

# PersonProduct

## What it is

A row in the `person_products` table representing one (person,
temporal_product) purchase. Created when a member completes a
membership purchase or an admin grants entitlement on their behalf.
Carries the optional `Transaction.id` that paid for it.

The row exists ⇒ the holder has the entitlement. Removing the row ⇒
the entitlement is revoked. No expiration column today — entitlement
ends when the row is deleted (typically via `/membership/upgrade`,
which deletes existing Membership-category rows before inserting a new one).

## Key fields

- `person_uuid`, `product_id` — the (person, TemporalProduct) pair.
- `transaction_id` — pointer to the `Transaction` that paid for it
  (nullable for free or admin-granted memberships).
- `granted_at`, `granted_by_uuid` — audit fields.

## Invariants

- **At most one Membership-category PersonProduct per person at a time.**
  `/membership/upgrade` enforces this by deleting all existing
  Membership-category rows for the user before inserting the new one
  (in a single transaction). This is the candidate
  `rule::membership::single_membership_personproduct`.

- Entitlement is checked **dynamically** on every gated action — there
  is no caching layer. `_has_boat_management` queries this table at
  request time.

## Relationships

- **Belongs to** a `Person` via `person_uuid`
- **Belongs to** a `TemporalProduct` via `product_id`
- **Optionally references** a `Transaction` via `transaction_id`

## Technical anchor

- **Model**: `concorda-api/models/person_product.py::PersonProduct`
- **Boat-management check**: `concorda-api/services/approvals.py::_has_boat_management`
- **Upgrade endpoint**: `PUT /api/profile/membership/upgrade`
  (`routers/profile.py:1373-1388`).
