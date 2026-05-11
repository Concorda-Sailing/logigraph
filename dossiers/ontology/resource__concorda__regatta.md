---
node_id: resource::concorda::regatta
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 6581249a11ddbeed6cfc5ce0130174b961338168043155e1bd565e2216b4c87f
---

# Regatta

## What it is

A row in the `regattas` table representing one race or race-day in the
sailing calendar. Carries `name`, `slug`, `start`/`end`, `scoring_system`,
`qualifier` (`Q`/`P`/`SH`/`O`/etc.), `course_type`, `region_uuid`, and
optionally a parent `series_uuid`. Each Regatta typically materializes as
an `Event` row (with `event.regatta_id = regatta.id`); members register
or bookmark via the Event, not the Regatta directly.

## Key fields

- `name`, `slug`, `start`, `end` — identity + window.
- `scoring_system` — list of rating systems used (e.g. `["PHRF", "ORR-Ez"]`).
- `qualifier` — JSON list of single-letter codes; canonical values are
  `Q, P, SH, O, J, S, W, H` (Q and P mutually exclusive).
- `course_type` — one of `buoy`, `windward/leeward`, `navigation`,
  `distance`, `government marks`, `fixed`. Pursuit is a *qualifier*
  (`P`), not a course type.
- `region_uuid` — geographic grouping (e.g. Boston Harbor).
- `oa_uuid` — legacy single-OA pointer; canonical is the M2M via
  `OrganizationRegatta`.
- `series_uuid` — optional parent series.

## Relationships

- **Belongs to** an `Organization` via `OrganizationRegatta` (M2M; legacy
  single column `oa_uuid` still exists).
- **Optionally belongs to** a `Series` via `series_uuid`.
- **Materializes as** an `Event` (`event.regatta_id`).

## Vocabulary notes

The qualifier / course_type / scoring_system vocabularies are documented
in `docs/regatta/rules.md` and consumed by an LLM-assisted regatta-entry
workflow — naming/qualifier rules are baked into extraction prompts.

## Technical anchor

- **Model**: `concorda-api/models/regatta.py::Regatta`
- **Read schema**: `concorda-api/schemas/regatta.py::RegattaRead`
- **OA join**: `OrganizationRegatta` (M2M; managed via
  `services/organizing_authorities.py::set_regatta_oas`).
