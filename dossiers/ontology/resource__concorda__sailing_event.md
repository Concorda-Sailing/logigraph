---
node_id: resource::concorda::sailing_event
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 40368d2d6bca6e5faaf9fdebc183f6b6889560d588e29c6eb57399f7293e06cc
---

# SailingEvent

## What it is

A row in the `sailing_events` table representing one captain's
per-boat plan for participating in one `Event`. The `(event_uuid,
boat_uuid)` pair is the de-facto unique key — multiple captains can
each have their own SailingEvent on the same Event. Carries the
logistics (`dock_time`, `departure_time`, `estimated_duration`,
locations, notes), the per-race position snapshot (`positions_needed`),
and the crew-recruitment knobs (`crew_pool_id`, `accept_crew_requests`,
`boat_config_id`).

## Key fields

- `event_uuid`, `boat_uuid` — the (event, owner-boat) pair. Resolved
  caller-scoped via `BoatCrew(role='owner')`.
- `dock_time`, `departure_time`, `arrival_time`, `estimated_duration` —
  logistics; tz-aware via `UtcDateTime`.
- `departure_location`, `arrival_location`, `notes` — text fields.
- `crew_pool_id` — optional pointer to a saved `CrewPool` for this boat.
- `boat_config_id` — pointer to the active `BoatConfig` for this race
  (drives slot count + position rendering).
- `accept_crew_requests` — per-race toggle that drives the
  "Accepting Crew" badge (see commit `b67d359`).
- `positions_needed` — snapshot of `Boat.positions` at SE-create time.
- `crew_confirmed` — captain's "roster locked" toggle.
- `event_subtype` — `race`, `delivery`, `training`, `cruise`, `other`.

## Relationships

- **Belongs to** an `Event` via `event_uuid`
- **Belongs to** a `Boat` via `boat_uuid`
- **Has many** `EventCrew` rows (the crew roster for this race)
- **Optionally references** a `CrewPool` via `crew_pool_id`
- **Optionally references** a `BoatConfig` via `boat_config_id`

## Visibility

Visible to: the boat's owner (captain), all crew on this SailingEvent,
and admins. Peer crew see other crew with PII gated by
`rule::crew_visibility::peer_pii_resume_gated`.

## Technical anchor

- **Model**: `concorda-api/models/sailing_event.py::SailingEvent`
- **Upsert endpoint**: `PUT /api/events/{event_id}/sailing-event` —
  caller-scoping via owner-`BoatCrew` join is load-bearing (`event_uuid`
  alone is insufficient).
- **Schedule rule**: SailingEvents on co-owned boats are source #5 of
  `_build_schedule_item_for_event` per
  `rule::schedule::canonical_listing`.
- **Calendar emails**: dock/logistics changes emit `logistics_set` /
  `logistics_updated` / `event_canceled` `.ics` mails to active crew
  (`invited`, `accepted`, `confirmed`).
