---
node_id: rule::payments::transaction_person_binding
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 59154d4c9e677cc47da40834376c720000d2eb30d3cb6ea27f9ff380ce1772d0
fan_out: 3
---

# Redeeming a paid transaction requires matching person binding

## The rule

A `Transaction` row represents a payment in flight or completed. It
optionally carries `person_id`: the buyer's Person row, or `NULL` if
the purchase was made by a guest (someone with no account yet).

When that Transaction is later *redeemed* (used to confirm an event
registration, grant an entitlement, etc.), the redemption code path
must verify:

- **Authenticated redeemer**: `Transaction.person_id == current_user.id`.
  Allow.
- **Guest redeemer** (no current_user): `Transaction.person_id IS NULL`.
  Allow.
- **Mismatch**: `Transaction.person_id IS NOT NULL` and `!=
  current_user.id`. **Reject.**
- **Asymmetric NULL**: `Transaction.person_id IS NULL` but
  `current_user.id IS NOT NULL` — this is the lazy-promote case
  (user beats the Stripe webhook to sign up). Allow, *and* promote
  the Transaction by setting `person_id = current_user.id`.

The shape of the check is "match or both-NULL," not "either-side-set-
or-match." Tightening it to require non-NULL on both sides breaks
guest checkout. Loosening it to allow any user with a valid token
breaks the security premise.

## Why it exists

Pre-fix (before commit `74962cb`), redemption checked the
`transaction_id` exists and is in a `paid` state — but did *not*
check who paid. Any authenticated user could pass another user's
`transaction_id` to the registration endpoint and complete a
registration on someone else's payment. The fix was to add the
person-id binding check.

Guest checkout (commit `3750138`) deliberately allows the
NULL-NULL path: a non-authenticated buyer can pay and immediately
redeem in the same anonymous session. The buyer is identified by the
`transaction_id` itself, not by a Person row. Later, if the buyer
signs up, the webhook lazy-promotes the Transaction to point at the
new Person row.

The asymmetric-NULL case (`person_id IS NULL`, `current_user.id IS
NOT NULL`) is real and common: user pays via Stripe → user creates
an account in the success-page flow → user lands on the registration
confirmation endpoint *before* the Stripe webhook has had a chance
to set `Transaction.person_id`. The endpoint must accept this case
and bind the Transaction in the process.

## Examples

- **Bob (signed in) pays for an event registration.** `create-intent`
  sets `Transaction.person_id = Bob`. `register_for_event` confirms
  with `transaction_id`; the match check passes; registration
  completes.
- **Bob (signed in) tries to redeem Carol's transaction_id.**
  `Transaction.person_id = Carol`. Check rejects with 403.
- **Anonymous guest pays + redeems in the same session.**
  `create-intent` sets `person_id = NULL`. `register_for_event` is
  called with no auth bearer; both sides are NULL; check passes.
- **Anonymous guest pays, then signs up before webhook fires.**
  `create-intent` set `person_id = NULL`. User creates account, lands
  on `/register?session_id=...` flow, which calls
  `register_for_event` with auth. `current_user.id` is set,
  `Transaction.person_id` is still NULL. Lazy-promote branch: bind
  `Transaction.person_id = current_user.id`, continue, succeed.
- **Anonymous guest pays, signs up later (after webhook).** Webhook
  sets `Transaction.person_id` via email match. Subsequent redemption
  goes through the normal match branch.

## Counter-examples (what the rule does NOT do)

- It does **not** apply to *reading* transactions for diagnostic
  purposes. Admin transaction listings have their own scoping.
- It does **not** mean a Transaction can only be redeemed once.
  Idempotency / replay protection is a separate concern (handled by
  the `EventRegistration` row, not the Transaction itself).
- It does **not** require email matching as part of the binding
  check. The binding is by `person_id`, not by email. Stripe-side
  email matching is what the *webhook* uses to set `person_id` for
  guest tx, but redemption only looks at the Person foreign key.

## Decision table

| Caller authenticated? | `Transaction.person_id` | Outcome at redemption                |
|------------------------|--------------------------|--------------------------------------|
| Yes                   | == `current_user.id`     | Allow                                |
| Yes                   | NULL                     | Allow + bind (lazy-promote)          |
| Yes                   | != `current_user.id` (set) | **Reject** (403)                   |
| No (guest)            | NULL                     | Allow (guest checkout)               |
| No (guest)            | non-NULL                 | **Reject** (the tx already has a Person; an anonymous session can't claim it) |

The cardinal mistake is conflating the third and fifth rows ("set on
the tx side, mismatch on the caller side") with the second row
("NULL on the tx side"). They both involve a non-matching `person_id`
on the tx, but only one is the legitimate guest-checkout path.

## Surfaces

- **Redemption sites** (all must match the decision table):
  - `POST /api/events/slug/{slug}/register` (events.py:1694-1727) —
    the canonical "use this paid transaction to confirm my
    registration" endpoint.
  - Any other future redemption endpoint (refund-reissue, transfer,
    etc.) — the rule generalizes.
- **Transaction creation** (where `person_id` gets set):
  - `POST /api/payments/create-intent` — sets `person_id =
    current_user.id` if authenticated, NULL otherwise.
- **Stripe webhook** (where `person_id` gets *bound* after the fact
  for guest tx):
  - `POST /api/payments/webhook` (payments.py:474-503) — match by
    email, promote NULL → Person.id.

## Gotchas

- **The lazy-promote branch is easy to forget.** A naive
  implementation reads "either match or both NULL" and rejects when
  `current_user` is set but `Transaction.person_id` is NULL. That
  breaks the post-pay sign-up flow. The branch must explicitly
  detect this case and bind.
- **Email matching belongs in the webhook, not in the redemption
  endpoint.** Don't reach for `Transaction.email == current_user.email`
  as a redemption check; the source of truth on the redemption side
  is `person_id`, and email matching there is a privacy leak vector.
- **The webhook is racy with the user's own redemption.** Both will
  try to set `Transaction.person_id`. Use `INSERT ... ON CONFLICT`
  or a single-row UPDATE with a WHERE-clause idempotency check —
  don't blindly overwrite.
- **The `NULL IS NULL` check in SQL is `IS NULL`, not `= NULL`.** A
  hand-written SQL query that does `WHERE person_id = :user_id`
  with `:user_id` bound to None will silently fail. Use SQLAlchemy
  comparison helpers or an explicit `is_(None)` clause.

## Technical anchor

- **Canonical redemption check**:
  `concorda-api/routers/events.py::register_for_event`
  (around line 1694) — read this when adding a new redemption path.
- **Lazy-promote branch**: `events.py:1715-1724` — the in-redemption
  `Transaction.person_id = current_user.id` write.
- **Webhook promote**: `concorda-api/routers/payments.py:474-503`
  — match by email, set `person_id`.
- **History commits**: `74962cb` (the original security fix),
  `3750138` (guest-checkout NULL-NULL path).
- **Adjacent ontology**: `resource::concorda::transaction`,
  `resource::concorda::person`, `role::system::member`.
