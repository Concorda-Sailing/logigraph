---
node_id: role::system::event_manager
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: e9c4bbe3e42f22f87c68841f77f92d375e18041292bd41de2640d50c32d8296e
---

# Event Manager

## Plain definition

An Event Manager is a Member with a `UserRole(role='event_manager', ...)`
row. They have the `events.edit` permission and can create, update,
and delete regattas, events, and the products attached to them
(tickets, discounts). Org-scoped via `UserRole.organization_id` in
the post-Tier-C world.

## They can

- Create regattas via `POST /api/regattas` (subject to OA scoping).
- Edit and delete regattas they have scope on
  (`_require_regatta_org_scope`).
- Create events via `POST /api/events` and admin event endpoints.
- Manage event products (tickets) and discounts.
- View and manage event registrations.
- Use the LLM-assisted NOR/SI extraction tools.

## They cannot

- Mutate resources owned by an Organization they do not administer
  (Tier-C scoping via `_require_event_org_scope` etc.).
- Modify org-level billing or membership configuration (those require
  `org_admin` / `membership_admin`).
- Grant or revoke other people's `UserRole` rows.

## Becomes one when

- A `system_admin` or `org_admin` of the Organization grants the role
  via the admin user-management endpoints.

## Stops being one when

- The role is explicitly revoked.

## Examples

- **Eve runs HYC's regatta calendar.** She holds `UserRole(role=
  'event_manager', organization_id=HYC)`. She can create regattas
  tagged to HYC, edit their tickets and discounts, and run the
  registration desk. She cannot edit BBC's regattas.

## Distinctions

- **Event Manager is not org_admin.** Event Manager has the events
  surface; org_admin has the broader club-administration surface.
- **`events.edit` is the permission, not the role name.** The
  permission is the actual gate; the role is the bundle that grants
  it. A future `org_admin` row may also carry `events.edit`.

## Technical anchor

- **Predicate**: `UserRole.role = 'event_manager'` (with `organization_id`
  for scope)
- **Level**: 30
- **Permission granted**: `events.edit`
- **Defined in**: `concorda-api/models/role.py::Role` (seeded by migrations)
- **Tier-C scoping**: `_require_event_org_scope`, `_require_regatta_org_scope`,
  `_require_oa_scope`
