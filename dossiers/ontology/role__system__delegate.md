---
node_id: role::system::delegate
node_kind: ontology
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 6b6b77a854b61129a859753ed9ac1a2f0ded68b269c0ca803b3193f01aeb71b0
---

# Delegate

## Plain definition

A Delegate is a Member with a `UserRole(role='delegate', organization_id=X)`
row. They have elevated permissions within Organization X — typically
managing event rosters, club contact info, and similar org-scoped
operations — but not the full `org_admin` capability set.

A Person can be a Delegate of one Organization and not another. The
role is always org-scoped (no global Delegates).

## They can

- Manage event-level details for events owned by their Organization
  (subject to `events.edit` permission).
- Edit the org's `ContactRole` rows for stewards, fleet captains, etc.
- Send communications scoped to their Organization (if granted).

## They cannot

- Modify the Organization's billing contact or membership configuration
  (those require `org_admin` or `membership_admin`).
- Create or delete the Organization itself.
- Grant or revoke other people's `UserRole` rows.
- Take actions on resources owned by other Organizations (per the
  Tier-C scoping enforcement).

## Becomes one when

- A `system_admin` or `org_admin` of the Organization grants the role
  via `POST /api/roles/person/{person_id}` with
  `{role: "delegate", organization_id: X}`.

## Stops being one when

- The role is explicitly revoked by an admin.
- The target Person row is deleted.

## Examples

- **Eve is the steward at HYC.** An HYC org_admin grants her
  `UserRole(role='delegate', organization_id=HYC)`. She can now edit
  the steward contact card and help manage event rosters for HYC
  regattas. She cannot edit BBC's events.

## Distinctions

- **Delegate is not org_admin.** Delegates have a narrower permission
  set. The hierarchy is `member < delegate (20) < org_admin (50) <
  system_admin`.
- **Delegate is always org-scoped.** There is no "global delegate."
  `UserRole.organization_id` is required for this role in practice.

## Technical anchor

- **Predicate**: `UserRole.role = 'delegate' AND UserRole.organization_id = X`
- **Level**: 20
- **Defined in**: `concorda-api/models/role.py::Role`
- **Granted via**: `POST /api/roles/person/{person_id}` (admin-gated)
