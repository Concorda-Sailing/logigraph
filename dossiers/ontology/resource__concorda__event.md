---
node_id: resource::concorda::event
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: c126f3fb34d57b68ed39d80b8c2c1540cdc30f58d677c0bb1200f75aecca5786
---

# Event

## What it is

A row in the `events` table representing one item on the calendar.
Created either as part of a regatta calendar publication (linked via
`regatta_id`), as an admin-curated social event, or as a personal
"bookmark" the user added to their own schedule. The `category` field
discriminates: `regatta`, `social`, `personal`.

## Key fields

- `name`, `date`, `end_date` — identity + window.
- `category` — `regatta` | `social` | `personal`.
- `regatta_id` — optional pointer to a `Regatta` row when this event is
  the calendar materialization of a race.
- `source_event_id` — when a user bookmarks an event, this points back
  to the canonical event.
- `owner_id` — for `personal` events, the person who created the
  bookmark.
- `slug` — non-unique across personal events; per commit `4fd165d`,
  personal events carry `slug = None` (not `""`) to dodge SQLite's
  NULL-allowed UNIQUE collision.
- `members_only` — boolean; gates public registration.
- `image_url`, `description`, `location`, `price`.

## Relationships

- **Optionally references** `Regatta` via `regatta_id`
- **Has many** `SailingEvent` (one per captain-boat pair fielded for the event)
- **Has many** `EventRegistration` (paid ticket signups)
- **Has many** `PersonEvent` (schedule bookmarks)
- **Has many** `EventCrew` rows (through `SailingEvent`)

## Visibility rules

- Personal events (`category='personal'`) are **owner-only** —
  excluded from every public listing (per the implicit invariant
  flagged in `CANDIDATES.md::rule::events::personal_event_excluded_from_public_listings`).
- Members-only events 401 anonymous callers.

## Technical anchor

- **Model**: `concorda-api/models/event.py::Event`
- **Read schemas**: `concorda-api/schemas/event.py::EventRead`,
  `EventReadWithRegatta`.
- **Schedule rule**: events appear on a user's schedule via five
  sources (owned, bookmarked, registered, crew, co-owned-SE) — see
  `rule::schedule::canonical_listing`.
