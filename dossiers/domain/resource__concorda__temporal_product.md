---
node_id: resource::concorda::temporal_product
node_kind: domain
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: f2b3e085b7d61e5bf4e0819633c1239a500fcff53f7998a8e2d14ea04815ac0f
---

# TemporalProduct

## What it is

A row in the `temporal_products` table representing one year's worth
of a purchasable thing — annual memberships ("Family Membership 2026"),
event registration packages, etc. Carries the `grants_*` flags that
turn into actual capabilities once purchased.

Distinct from:
- **Product** — per-event tickets (one-off, not year-scoped).
- **Merchandise** — physical goods.
- **PersonProduct** — the row that records "person X has temporal product Y" after purchase.

## Key fields

- `slug`, `name`, `description`, `category` (Membership | Event)
- `year` — calendar year scope.
- `price`, `effective_date`, `end_date`, `publish_date` — purchase window.
- `is_active` — soft-disable flag.
- `event_id` — for Event-category products, links to the event.
- **`grants_boat_management`** — entitles holders to register/edit boats.
  Drives `_has_boat_management` and the candidate
  `rule::coowner::eligibility_at_accept` (Boat Owner membership required
  to accept a co-owner invite).
- **`grants_event_discount`** — qualifies the holder for membership-based event discounts.
- **`grants_directory_listing`**, **`grants_crewfinder_visibility`** — display gates.
- `min_age`, `max_age`, `requires_boat` — eligibility constraints.

## Year-rollover behavior

The admin-only `GET /api/temporal-products` endpoint triggers a lazy
year-copy when invoked with both `year` and `category` for an empty
bucket — `_copy_products_from_previous_year` runs and commits new rows.
The public `/available` path does NOT do this (commit `ec53704` closed
that surface).

## Relationships

- **Has many** `PersonProduct` (one per purchase)
- **Has many** `Merchandise` via `TemporalProductMerchandise` junction
- **Optionally references** an `Event`

## Technical anchor

- **Model**: `concorda-api/models/temporal_product.py::TemporalProduct`
- **Read schema (admin)**: `concorda-api/schemas/temporal_product.py::TemporalProductRead`
- **Public read schema**: `TemporalProductPublic` (narrower; no grants flags)
- **Entitlement check helper**: `services/approvals.py::_has_boat_management`
