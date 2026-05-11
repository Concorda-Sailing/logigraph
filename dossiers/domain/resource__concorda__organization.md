---
node_id: resource::concorda::organization
node_kind: domain
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: aadd05fb0188e713244e041acfa17a61219f142113e86c1def38b28aab32cdef
---

# Organization

## What it is

A row in the `organizations` table representing one yacht club or
sailing association. Carries identity (name, abbreviation, burgee URL),
address, contact info (VHF channel, region), and pointers to key
contact persons (steward, billing contact, fleet captain). Owns the
regattas, series, and events tagged to it via M2M tables.

## Key fields

- `name`, `abbreviation` — display labels.
- `org_type` — typically "yacht_club" or similar.
- `burgee_url`, `vhf_channel`, `region`, `address` (JSON).
- `steward_id`, `billing_contact_id`, `fleet_captain_id` — Person UUIDs
  (no FK enforcement).
- `reciprocity_with` — list of org IDs (reciprocity arrangements).
- `parent_org_id` — optional parent for hierarchical orgs (unused today).

## Relationships

- **Has many** `OrganizationRegatta` (M2M to `Regatta`)
- **Has many** `OrganizationEvent` (M2M to `Event`, relationship=`organizing_authority`)
- **Has many** `OrganizationSeries` (M2M to `Series`)
- **Has many** `UserRole` rows scoped to this org (`organization_id` set)
- **Has many** `ContactRole` rows (admin contacts: stewards, captains)

## Authorization boundary

This is the unit of cross-org enforcement (Tier C scoping per commit
`058aa8c`):

- Mutating endpoints that touch an org-owned resource must funnel
  through `AuthUser.can_administer_orgs(owning_org_ids)` after resolving
  the resource's owning-org set.
- `_require_org_admin_scope`, `_require_regatta_org_scope`,
  `_require_event_org_scope`, `_require_oa_scope` are the chokepoints.

The candidate `rule::auth::tier_c_org_scope_chokepoint` in `CANDIDATES.md`
formalizes this invariant.

## Technical anchor

- **Model**: `concorda-api/models/organization.py::Organization`
- **Read schema**: `concorda-api/schemas/organization.py::OrganizationRead`
- **Resolver**: `services/organizing_authorities.py::get_owning_org_ids_for_event/_regatta/_series/_product`
- **Auth chokepoint**: `auth_middleware.py::AuthUser.can_administer_orgs`
