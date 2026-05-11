---
node_id: resource::concorda::transaction
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: d040666d69bcbd2bf8fcaddbc9ea417a4126df27e072586b16a4db73db5ac326
---

# Transaction

## What it is

A row in the `transactions` table representing one financial event —
a Stripe-backed paid registration or membership purchase, or a
synthetic $0 row for free memberships and pro-rated upgrades. The
canonical ledger between Stripe (async, webhook-driven) and Concorda's
synchronous "register now" flows.

## Key fields

- `person_id` — buyer's Person UUID. **Nullable** for guest checkout
  (anonymous registration).
- `product_id`, `product_type` — discriminator: `"Product"` for event
  tickets, `"TemporalProduct"` for memberships.
- `amount` — `Numeric(10,2)` (never float).
- `status` — `Pending`, `Completed`, `Failed`, `AmountMismatch`,
  `Refunded` (unused today).
- `external_reference` — Stripe PaymentIntent id, **UNIQUE**.
- `expected_quantity` — order size, used by `EventRegistration`
  redemption to cap multi-ticket purchases.
- `date`, `notes`.

## Security boundary

Paid redemption (mintng `EventRegistration` or `PersonProduct`) requires:
- `Transaction.status == "Completed"` AND
- `Transaction.person_id == current_user.id` (or BOTH NULL for guest).

The NULL-NULL branch is intentional, not a fallback hole — guest
checkout pays before account creation. The candidate
`rule::payments::transaction_person_binding` formalizes this.

The fix `74962cb fix(security): bind paid registrations` introduced
this binding after a vulnerability where a logged-in user could replay
another user's completed payment.

## Relationships

- **Optionally belongs to** a `Person` via `person_id`
- **Referenced by** `EventRegistration.transaction_id`
- **Referenced by** `PersonProduct.transaction_id`
- **Externally bound to** a Stripe PaymentIntent via `external_reference`

## Lifecycle

```
Pending ─Stripe webhook (payment_intent.succeeded)──► Completed
        ─Stripe webhook (payment_intent.payment_failed)──► Failed
        ─amount mismatch detected in webhook──► AmountMismatch
        ─/register lazy-promote path──► Completed  (parallel writer)
```

## Technical anchor

- **Model**: `concorda-api/models/transaction.py::Transaction`
- **Webhook handler**: `concorda-api/routers/payments.py::webhook`
- **Lazy-promote**: `concorda-api/routers/events.py:1715-1724`
- **Security commit**: `74962cb` (`person_id` binding)
