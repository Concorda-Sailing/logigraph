---
node_id: role::system::system_admin
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: ad8c9e44e85f7c426afa04194c4550f1c81214bd79067dade0df0c062ab60caf
---

# System Admin

## Plain definition

A System Admin is a Member with a `UserRole(role='system_admin')` row.
They have global, unscoped authority — they can grant any role
(including other system_admins, subject to the privilege-escalation
guard), mutate any resource regardless of organization, and configure
system-level settings.

This role is reserved for the site operator (Logan today) and a small
trusted set.

## They can

- Grant or revoke any `UserRole` (subject to the level guard — a
  `system_admin` cannot demote themselves below another `system_admin`
  unless they accept the consequences).
- Mutate resources owned by any Organization (bypasses Tier-C scoping).
- Configure `OrgConfig` (timezone, branding, default membership, rate
  limits, error-alert recipient).
- Configure payment settings (Stripe mode, keys).
- Access all admin endpoints regardless of org.

## They cannot

- Bypass payment for paid purchases (no special bypass).
- Read passwords (those are bcrypt-hashed and never readable).
- Edit the system itself (code/config changes happen out-of-band).

## Becomes one when

- An existing `system_admin` grants the role via `POST /api/roles/person/{id}`.
- Historically: seeded into the database during initial setup
  (`migrations/seed_*.py`).

## Stops being one when

- An existing `system_admin` revokes the role.

## Examples

- **Logan.** He holds `UserRole(role='system_admin')`. He can do
  anything in any org.
- **Initial site setup.** The very first `system_admin` is seeded by
  the install migration; subsequent ones are granted by existing
  system_admins.

## Distinctions

- **System Admin is unscoped.** It has no `organization_id`. Don't
  conflate with org_admin (which has org scope).
- **System Admin is not the auth bearer.** Authentication (who you
  are) is via `AuthToken`/`AgentToken`. Authorization (what you can
  do) is via roles. A system_admin still needs a valid bearer.

## Technical anchor

- **Predicate**: `UserRole.role = 'system_admin'`
- **Level**: 100 (highest)
- **Bypasses**: Tier-C `can_administer_orgs` returns True for system_admins
  regardless of the owning-org set.
- **Privilege escalation guard**: candidate
  `rule::auth::privilege_escalation_level_guard` — no role can be granted
  with `level > granter.max_level`.
