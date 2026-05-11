---
node_id: role::system::org_admin
node_kind: ontology
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: a11e6bec9f201592b84c0a153ec9f31c8a136b6469ba8fd469070a4d863ed221
---

# Organization Admin

## Plain definition

An Organization Admin is a Member with a `UserRole(role='org_admin',
organization_id=X)` row. They have the broadest authority within
Organization X short of `system_admin` — they can grant and revoke
other roles within the org, edit all org-level configuration, and
administer all of the org's owned regattas, series, events, products,
and memberships.

## They can

- Grant and revoke `UserRole` rows within their Organization (limited
  by privilege-escalation guards — they cannot grant a role higher
  than their own level).
- Edit the Organization's configuration (name, branding, address,
  contact info).
- Administer all events, regattas, series, products, and memberships
  scoped to the Organization.
- Promote a Member to `delegate`, `event_manager`, `treasurer`, or
  `membership_admin` within the org.

## They cannot

- Grant `system_admin` (level guard).
- Mutate resources owned by other Organizations (Tier-C scoping
  enforced via `_require_*_org_scope` chokepoints).
- Modify the `system_admin` ladder or change a global-scope role.

## Becomes one when

- A `system_admin` grants the role.
- Historically (per `project_org_admin_grandfather`), org_admin rows
  with `NULL organization_id` exist as a grandfather bypass; Tier-C
  scoping treats those as global. Revisit after Tier-C ships.

## Stops being one when

- A `system_admin` revokes the role.

## Examples

- **Bob is the club commodore at MBSA.** He holds `UserRole(role=
  'org_admin', organization_id=MBSA)`. He can grant Eve `event_manager`
  for MBSA, edit MBSA's branding and contact info, and administer all
  of MBSA's regattas. He cannot edit HYC's events.

## Distinctions

- **Org Admin's scope is one Organization.** Don't confuse with
  `system_admin`, which is unscoped.
- **Org Admin is not the steward.** Steward is a `ContactRole` (an
  admin-visible contact card). Org Admin is the system-level
  administrative authority.

## Technical anchor

- **Predicate**: `UserRole.role = 'org_admin' AND UserRole.organization_id = X`
  (or NULL for grandfathered rows)
- **Level**: 50
- **Tier-C scoping**: `_require_org_admin_scope`, `_require_event_org_scope`,
  `_require_regatta_org_scope`, `_require_oa_scope`
- **Privilege escalation guard**: candidate
  `rule::auth::privilege_escalation_level_guard`
