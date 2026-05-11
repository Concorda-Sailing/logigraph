---
node_id: role::system::treasurer
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 71c6d251ebd18d786d395f5c8c75f7bd8d15518360818525d94897f6b356b41c
---

# Treasurer

## Plain definition

A Treasurer is a Member with a `UserRole(role='treasurer', ...)` row.
They have authority over the org's financial flows: payment
configuration, transaction visibility, and revenue reporting. Refund
endpoints are not currently shipped but would land in this role's
permission set.

## They can

- View `Transaction` rows scoped to the Organization (when admin
  transaction-listing endpoints exist).
- Configure the org's payment settings (Stripe key, mode).
- Review billing-contact assignments and edit them in concert with
  `org_admin`.

## They cannot

- Issue refunds today (no refund endpoint exists yet — when it does,
  this role would gain that permission).
- Modify event ticket prices (that's `event_manager`/`events.edit`).
- Grant or revoke other people's `UserRole` rows.

## Becomes one when

- A `system_admin` or `org_admin` of the Organization grants the role.

## Stops being one when

- The role is explicitly revoked.

## Examples

- **Alice manages MBSA's finances.** She holds `UserRole(role=
  'treasurer', organization_id=MBSA)`. She can review transactions
  and update the Stripe configuration. She cannot edit MBSA's events
  or modify members.

## Distinctions

- **Treasurer is not the `billing_contact`.** The billing contact is
  a `ContactRole` row pointing at a Person (who may or may not be the
  treasurer). The Treasurer role is the system-level permission to
  *administer* financial settings; `billing_contact` is the labeled
  human point of contact.

## Technical anchor

- **Predicate**: `UserRole.role = 'treasurer'`
- **Level**: 30
- **Defined in**: `concorda-api/models/role.py::Role` (seeded)
- **Adjacent domain**: `resource::concorda::transaction`
