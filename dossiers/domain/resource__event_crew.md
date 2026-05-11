---
node_id: resource::concorda::event_crew
node_kind: domain
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-10
last_reviewed_against_hash: 2efa547bca613b74701ff9eaf5821224d92bc0d2dc22577aba6ae00fe28ac002
---

# EventCrew

## What it is

A row in the `event_crew` table representing one person's crew slot for
one sailing event. Created when a boat owner adds someone to the pool
or sends an invite, when a sailor self-nominates via crew-request, or
when an alternate is auto-promoted by the roster service.

Unique on `(sailing_event_uuid, person_uuid)` — one person can hold at
most one slot per sailing event. A person may have many EventCrew
rows (one per event they're involved with).

## Key fields

- `status` — lifecycle state. Canonically one of `pool`, `invited`,
  `accepted`, `declined`, `confirmed`, `requested`. See
  `rule::event_crew::status_enum` for the canonical enum + decision
  table. The `EventCrewStatus(str, Enum)` class in
  `concorda-api/models/event_crew.py` is the source of truth.
- `role` — `main` or `alternate`. Drives roster evaluation; alternates
  are promoted to main when a main crew declines.
- `priority` — integer ordering within the boat's crew for an event.
- `position_name` — optional foredeck/main/etc., picked by the crew
  member or assigned by the owner.
- `invited_by_uuid` — who issued the invite. Drives reply-to on emails.
- `responded_by_uuid` — who marked the response. Conflated with
  responder identity in some flows; see open question on
  `rule::crew_visibility::peer_pii_resume_gated`.
- `self_selected` — true if the crew member picked their own position.

## Lifecycle (informal)

```
                      send_crew_invites
  set_crew_pool                ┌─────► invited ─────►  accepted ──confirm──► confirmed
        │                      │           │
        ▼                      │           └────────►  declined  (terminal)
       pool ─────────────────► │
        │                      │
        ▼                      │
       (rare: self auto-accept)│
                                ▼
  request_to_crew ─────────► requested ──────► accepted (also creates BoatCrew)
                                       └─────► declined (no BoatCrew side-effect)
```

## Relationships

- **Belongs to** a `SailingEvent` (which belongs to an `Event`).
- **Belongs to** a `Boat`.
- **References** a `Person` (the crew member).
- **Optionally references** a `Person` (the inviter via
  `invited_by_uuid`).

## Visibility

Crew rows are visible to: the row's own person (always); the boat's
owner (always); peer crew on the same boat (with PII gated by
`rule::crew_visibility::peer_pii_resume_gated`). Event managers and
admins see unfiltered.

## Technical anchor

- **Model**: `concorda-api/models/event_crew.py::EventCrew`
- **Schema (response)**: `concorda-api/schemas/event_crew.py::EventCrewRead`
- **Status enum**: `concorda-api/models/event_crew.py::EventCrewStatus`
- **Role enum**: `concorda-api/models/event_crew.py::EventCrewRole`
- **Roster service**: `concorda-api/services/crew_roster.py`
- **Invite dispatch**: `concorda-api/services/invite_dispatch.py`
