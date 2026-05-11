---
node_id: resource::concorda::boat
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 3e127128c14546fddfea79be23f0a230e456abc076873fc56a4ee338135aec87
---

# Boat

## What it is

A row in the `boats` table representing one sailing vessel. Created by
`POST /api/profile/boats` (which seeds a `BoatCrew(role='owner',
status='active')` row in the same transaction). Carries the identifying
fields (name, sail number, class, length, manufacturer), location
metadata, picture/banner URLs, and operational hints (`positions`
default JSON, cap fields). The `Boat` itself does NOT carry ownership —
that lives on `BoatCrew`.

## Identity

Per the canonical Boat lookup contract, the **`(sail_number, name)`
pair** (after normalization) is the identity tuple. `sail_number` alone
is *not* unique across clubs — multiple J/24s with the same sail number
exist legitimately. The create endpoint enforces global uniqueness on
raw `sail_number` only (looser than the lookup-uniqueness convention);
see Boat model dossier for the asymmetry.

## Key fields

- `name`, `sail_number` — identity pair.
- `boat_class`, `length`, `manufacturer`, `year_built` — classification.
- `location_club`, `location_city`, `location_state`, `mooring_slip` —
  legacy flat columns. The newer `address` JSON dict is partially
  populated and read-only-on-read (writers don't sync it yet).
- `positions` — JSON list of `{name, location_x, location_y, count?}`,
  the default position template. Snapshotted into
  `SailingEvent.positions_needed` at event-create time; changes do not
  cascade.
- `picture_url`, `banner_url` — uploaded image URLs.
- `owner_ids` — legacy JSON array. **Read-only-legacy.** New code reads
  ownership via `BoatCrew(role='owner', status='active')`.

## Relationships

- **Has many** `BoatCrew` rows (owners + crew, by `role`/`status`)
- **Has many** `BoatConfig` rows (named position layouts)
- **Has one** `BoatResume` (recruitment bio for the boat finder)
- **Has many** `SailingEvent` rows (per-race plans)
- **Has many** `CrewPool` rows (saved crew groupings)
- **Has many** `PendingCrewInvite` rows (email-only crew invites)
- **Has many** `BoatPunchlistItem` rows (maintenance todos)

## Visibility

- Boat identity (name, sail_number, class) is public via boatfinder when
  `BoatResume.published = True`.
- Crew rosters and PII are gated by
  `rule::crew_visibility::peer_pii_resume_gated`.
- Owners see unfiltered.

## Technical anchor

- **Model**: `concorda-api/models/boat.py::Boat`
- **Read schema**: `concorda-api/schemas/profile.py::BoatRead`
- **Ownership predicate**: `BoatCrew.role='owner' AND BoatCrew.status='active'`
  (see `role::relational::boat_owner`).
- **Position snapshot**: `SailingEvent.positions_needed` is a snapshot,
  not a live reference. Cascade was attempted in commit `31aa70d`,
  reverted in `d54327b`.
