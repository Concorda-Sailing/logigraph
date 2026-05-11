---
node_id: relationship::event::is_organized_by
node_kind: domain
node_subkind: relationship
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 7bb93da80c16d45a11754475640903646bc7a2df5eafd2a614c7d486b6a7703b
---

# Event is organized by Organization

## What it is

A non-personal Event belongs to one or more Organizations (clubs).
That ownership determines who can administer the event — the Tier-C
scoping rule (`rule::auth::tier_c_org_scope_chokepoint`) funnels every
mutating endpoint through `AuthUser.can_administer_orgs(owning_org_ids)`,
where the owning-org set is resolved via this relationship.

## Predicate

Event E is organized by Organization O iff:
- `Event.organization_id = O`, OR
- `Event.regatta_id = R` AND `Regatta.organization_id = O` (or
  `O in Regatta.organizing_authority`).

## Mediation

`event.organization_id` (direct) or via `event.regatta_id` → `regatta`
(transitive through the regatta's owning club + OA list).

## Cardinality

`0..many`. Most events have one owning org. Co-hosted regattas can
list multiple in `organizing_authority`, in which case all those orgs
are equal organizers.

## Lifecycle

- **Set at creation** by the event manager who creates the regatta or
  event.
- **Mutable by org_admin** of an owning org, subject to Tier-C
  scoping.
- **Personal events** opt out of this relationship entirely — they
  have no `organization_id` and are owned by a Person via
  `event.owner_id` (see `relationship::event::is_owned_by_person`).

## Examples

- HYC creates the "Spring Regatta 2026" with `regatta.organization_id
  = HYC`. All Events in that regatta inherit HYC as their organizer.
- HYC and MBSA co-host a regional regatta. `regatta.organizing_
  authority = [HYC, MBSA]`. Either club's `org_admin` can administer
  the regatta and its events.

## Edge cases

- **Personal events** (`event.category = 'personal'`) have NULL
  `organization_id`. They are *not* "owned by no organization" — they
  are owned by a Person, a structurally different relationship.
  Surfaced as a separate relationship to keep the scoping logic
  unambiguous.
- **Co-hosting allows any-org-matches** for administration. A user
  who administers any one of the OA orgs can mutate. Tightening to
  "must administer all" is a design question.

## Technical anchor

- **Resolution helpers**: `routers/regattas.py::_require_regatta_org_scope`,
  `routers/regattas.py::_require_oa_scope`,
  `routers/products.py::_require_event_org_scope` (transitive).
- **Chokepoint**: `auth_middleware.py::AuthUser.can_administer_orgs`.
- **Adjacent rule**: `rule::auth::tier_c_org_scope_chokepoint`.
