---
node_id: rule::auth::tier_c_org_scope_chokepoint
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 6ea12651765ea6947e5650a0d84e7498f36c13e14e11f19779612022e77d372b
fan_out: 8
---

# Cross-org mutations must funnel through can_administer_orgs

## The rule

Any mutating endpoint that touches an organization-owned resource —
`Organization`, `Regatta`, `Event` (when owned by a club rather than a
person), `TemporalProduct`, `Discount`, `Series`, `ContactRole`,
billing contacts — must authorize through the same two-step pattern:

1. **Resolve the owning-org set** for the resource the call is about
   to mutate. For a regatta this is `Regatta.organization_id`; for a
   product it's the regatta of the event of the product (chain
   through). For an OA list it's all `organizing_authority` entries.
2. **Funnel the decision** through
   `AuthUser.can_administer_orgs(owning_org_ids)`. That is the
   chokepoint that knows about `org_admin` scope, `system_admin`
   bypass, and the (grandfathered) NULL-organization-id case.

Checking only that the caller is *an* `org_admin` is not sufficient:
an org_admin of HYC could otherwise mutate MBSA's regattas. The
caller's *scope* (which orgs they can administer) is what matters.

## Why it exists

Pre-Tier-C, several endpoints checked `role == "org_admin"` or
`role.level >= 50` without verifying the resource being mutated
belonged to an org the caller administered. The Tier-C audit (commit
`058aa8c`, 2026-05-05) found that any `org_admin` or `delegate` of
*one* club could mutate *any other* club's regattas, events, and
contacts.

The pattern has been a recurring regression vector: new endpoints
ship a role-type check and miss the resource-scope check. The fix
that landed centralizes the decision behind one helper —
`can_administer_orgs` — and a handful of `_require_*_org_scope`
chokepoints (`_require_org_admin_scope` for Organization,
`_require_regatta_org_scope` for Regatta, `_require_event_org_scope`
for Event/Product, `_require_oa_scope` for OA membership). Every new
mutating endpoint must use one of those, not roll its own.

There is a known grandfather case: some pre-Tier-C `UserRole(role=
'org_admin', organization_id=NULL)` rows exist. `can_administer_orgs`
treats `NULL` as "all orgs" — see `project_org_admin_grandfather`. Do
not narrow this without revisiting that memory.

## Examples

- **Eve is `org_admin` of HYC. She tries to `PUT /api/regattas/{mbsa-regatta-id}`.**
  The endpoint resolves the regatta's owning-org (MBSA), calls
  `can_administer_orgs({MBSA})`, and returns 403 because Eve only
  administers `{HYC}`.
- **Eve `PUT`s an HYC regatta.** Same path, `can_administer_orgs({HYC})`
  returns True, mutation proceeds.
- **Logan is `system_admin`.** Any owning-org set returns True from
  `can_administer_orgs` — system_admin is unscoped (the documented
  bypass).
- **An OA-list mutation on a regatta co-hosted by HYC + MBSA.**
  `_require_oa_scope` resolves both orgs; the caller must administer
  *at least one* (today's rule) to make the change.
- **Creating a regatta whose `organizing_authority` contains a club
  the caller does not administer.** `_require_oa_scope` rejects on
  POST so the caller cannot smuggle in a foreign org.

## Counter-examples (what the rule does NOT do)

- It does **not** apply to *read* endpoints. `GET /api/regattas/{id}`
  is publicly readable; the rule is about mutations.
- It does **not** replace `events.edit` (or other permission flags) —
  those gate "is this user capable in principle." The Tier-C check
  asks "is this user capable *for this specific resource*."
- It does **not** apply to person-owned events. Personal events are
  scoped by `Event.owner_id == current_user.id`, not by
  organization. See `rule::events::personal_event_excluded_from_public_listings`.
- The rule does **not** require the caller to administer *all* of a
  resource's owning orgs when there are multiple. Co-hosted regattas
  let *any* administering org make changes. (Whether that should
  tighten is an open design question.)

## Decision table

| Caller scope (`can_administer_orgs`) | Resource owning-org set | Outcome |
|--------------------------------------|--------------------------|---------|
| system_admin (unscoped)              | any                      | Allow   |
| org_admin/delegate of {X}            | {X}                      | Allow   |
| org_admin/delegate of {X}            | {Y} (different org)      | 403     |
| org_admin/delegate of {X}            | {X, Y} (co-hosted)       | Allow (any-match) |
| org_admin/delegate of {X}            | {Y, Z}                   | 403     |
| Grandfather: `UserRole(org_admin, organization_id=NULL)` | any   | Allow (legacy bypass — revisit per project_org_admin_grandfather) |
| member / unscoped                    | any                      | 403 (or 401 if no auth) |

The decisive question on every edit to a mutating endpoint on these
resources: *which `_require_*_org_scope` helper did I call before
performing the mutation?* If the answer is "none, I just checked
`current_user.role`", the edit violates this rule.

## Surfaces

- **Chokepoint helper** (not depgraph-tracked):
  `auth_middleware.py::AuthUser.can_administer_orgs(owning_org_ids)`
- **Per-resource scoping helpers** in `routers/`:
  - `_require_org_admin_scope(org_id)` — Organization mutations
  - `_require_regatta_org_scope(regatta_id)` — Regatta + nested
  - `_require_event_org_scope(event_id)` — Event + child products
  - `_require_oa_scope(organizing_authority_list)` — multi-org OA
- **Mutating endpoints that must funnel through one of the above** (sample —
  see `claims_code` for the canonical list):
  - `POST/PUT/DELETE /api/organizations/...` + nested contacts
  - `POST/PUT/DELETE /api/regattas/...`
  - `POST/PUT/DELETE /api/events/...` (when not personal)
  - `POST/PUT/DELETE /api/products/...`
  - Discount / Series mutations on org-owned regattas

## Gotchas

- **Reads that *expose* org-internal data also need scoping.** This
  rule is focused on mutations, but a parallel concern exists for
  reads — `GET /api/organizations/{id}/contacts` is org-scoped on the
  read side. Don't assume "read = safe."
- **CSV import endpoints look bulk but are still per-row mutations.**
  `POST /api/organizations/import/csv` and similar must scope each
  imported row, not blanket-allow the request.
- **The NULL grandfather case.** A `UserRole(role='org_admin',
  organization_id=NULL)` administers *all* orgs by current logic.
  This was preserved for migration safety. Do not narrow without
  updating `project_org_admin_grandfather` and migrating the rows.
- **`organizing_authority` is plural.** A regatta can be co-hosted.
  `_require_oa_scope` must check the *list*, not a single id.
  Co-hosted regattas where the caller administers any one org are
  allowed; this is by design, not laxity.
- **Don't roll a new scope helper.** If your endpoint needs a
  resource-to-owning-org resolution that isn't covered by one of the
  four helpers above, extend `auth_middleware.py` with a new helper
  that calls `can_administer_orgs` — don't inline the check.

## Technical anchor

- **Canonical chokepoint**: `auth_middleware.py::AuthUser.can_administer_orgs(owning_org_ids: set[UUID]) -> bool`
- **system_admin bypass**: lives inside `can_administer_orgs` — it short-circuits True for any owning-org set.
- **NULL grandfather**: lives inside `can_administer_orgs` — treats `UserRole.organization_id IS NULL` as "all orgs."
- **Per-resource helpers**: `routers/organizations.py::_require_org_admin_scope`, `routers/regattas.py::_require_regatta_org_scope`, `routers/regattas.py::_require_oa_scope`, `routers/products.py::_require_event_org_scope`.
- **History anchor**: commit `058aa8c` (Tier-C audit, 2026-05-05) is the canonical fix-commit; before it, role-only checks were the norm.
- **Adjacent ontology**: `role::system::org_admin`, `role::system::system_admin`, `resource::concorda::organization`.
- **Adjacent rule**: `rule::auth::privilege_escalation_level_guard` (sibling — role assignment scoping, different concern, same area).
