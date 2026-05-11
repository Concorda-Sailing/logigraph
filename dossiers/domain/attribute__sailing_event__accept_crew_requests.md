---
node_id: attribute::sailing_event::accept_crew_requests
node_kind: domain
subkind: attribute
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 0de827b227a7d4fdbb30f07f3d7f1fa4361c6983f121478d7d235c069c21e223
---

# accept_crew_requests

## What it is

A boolean column on `SailingEvent` (the captain's plan for one boat at
one event). When true, the boat is accepting unsolicited crew requests
for this specific race — sailors can submit a "request to crew" via
`POST /api/events/{id}/sailing-event/crew-request`, which creates an
EventCrew row with `status='requested'` for the captain to triage.

When false, the crew-request endpoint returns 403 — the boat is not
soliciting crew for this race.

## Predicate

`SailingEvent.accept_crew_requests == True` for the (event, boat) pair.

## Why it matters

This is the **per-race signal**, distinct from:

- **`BoatResume.accepting_crew`** — the boat-level recruitment posture
  ("Yes" / "Occasionally" / "No"). This is the captain bio, displayed
  on the boat finder.
- **`attribute::resume::published`** — the crewfinder opt-in on the
  Person side.

Commits `b67d359` and `6c9b5f3` deliberately split these. Before the
fix, the regatta-calendar "Accepting Crew" badge read from
`BoatResume.accepting_crew`, which was wrong — a boat could be
"accepting crew in general" but not for this specific race. The badge
should always read from this attribute on the SailingEvent.

## Lifecycle

Flips on when:
- The captain toggles it via the schedule detail or event-plan-panel UI,
  writing through `PUT /api/events/{id}/sailing-event` (the upsert
  endpoint).

Flips off when:
- The captain toggles it off.
- The SailingEvent is deleted (whole row goes; the attribute is moot).

## Technical anchor

- **Column**: `SailingEvent.accept_crew_requests` (Boolean, default False)
- **Defined in**: `concorda-api/models/sailing_event.py`
- **Endpoint gate**: `POST /api/events/{id}/sailing-event/crew-request` —
  403 if False.
- **UI badge**: regatta calendar "Accepting Crew" badge reads this
  (post-`b67d359`).
- **Related domain**: `resource::concorda::sailing_event`.
