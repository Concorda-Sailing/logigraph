---
node_id: role::system::membership_admin
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 71f31dfe34478e4a098bfb6885e8c24902755fb33e1fcb51d336d3e66da37e2d
---

# Membership Admin

## Plain definition

A Membership Admin is a Member with a `UserRole(role='membership_admin',
...)` row. They hold the `admin.memberships.view` and
`admin.memberships.manage` permissions, which gate all
`TemporalProduct` and `Merchandise` admin endpoints.

## They can

- List, create, edit, and delete `TemporalProduct` rows (memberships
  and event-scoped products).
- Edit `grants_*` flags (`grants_boat_management`, `grants_event_discount`,
  etc.) that drive entitlements.
- Manage the merchandise catalog and product-merchandise bundling.
- Manually grant `PersonProduct` entitlements outside of paid flows
  (admin grant path).

## They cannot

- Issue refunds (no refund flow exists).
- Modify other people's `UserRole` rows.
- Manage events or regattas (that's `event_manager`).
- Modify org-level configuration outside of memberships (that's
  `org_admin`).

## Becomes one when

- A `system_admin` or `org_admin` grants the role.

## Stops being one when

- The role is explicitly revoked.

## Examples

- **Carol runs MBSA's membership renewals.** She holds `UserRole(role=
  'membership_admin', organization_id=MBSA)`. She can roll over the
  membership catalog into a new year and edit the `grants_*` flags on
  individual products. She cannot edit events or regattas.

## Distinctions

- **Membership Admin is not the Boat-Owner-membership holder.** The
  *role* admins the product catalog; the *PersonProduct entitlement*
  is what makes someone a Boat Owner per
  `rule::coowner::eligibility_at_accept`.

## Technical anchor

- **Predicate**: `UserRole.role = 'membership_admin'`
- **Level**: 40
- **Permissions**: `admin.memberships.view`, `admin.memberships.manage`
- **Gated routes**: `/api/temporal-products/*`, `/api/merchandise/*`
