---
node_id: role::relational::event_captain
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 6f6e3016e35047264baaac6a96b1c5a05fa87b4429478dc6f42c10c02c686049
---

# Event Captain

## Plain definition

An Event Captain is the person fielding one of their boats at one
event. They are an active Boat Owner of the boat (`BoatCrew(role=
'owner', status='active')`) AND their boat has a `SailingEvent` row
for the event in question.

A single event can have many captains — one per fielded boat. The
captain owns the per-race logistics and crew roster for their
SailingEvent specifically; they do not have authority over other
captains' SailingEvents on the same Event.

## They can

- Edit the SailingEvent's logistics (`dock_time`, `departure_time`,
  `arrival_location`, `notes`, etc.).
- Set the crew pool (`crew_pool_id`) from their saved CrewPools.
- Toggle `accept_crew_requests` for this race.
- Invite specific crew members (transitions EventCrew rows pool →
  invited).
- Accept or reject crew-requests submitted by sailors.
- Mark crew responses on behalf of crew (verbal accepts/declines).
- Confirm the roster.
- Cancel their own SailingEvent (tears down EventCrew rows + emails).

## They cannot

- Edit other captains' SailingEvents on the same Event.
- Edit the underlying Regatta or Event (those require `event_manager`
  scope).
- Bypass crew-visibility rules — they see *their* boat's crew
  unfiltered, not other boats' crew.

## Becomes one when

- They (or a co-owner) call `PUT /api/events/{event_id}/sailing-event`
  with their boat's UUID, creating the (event, boat) SailingEvent row.

## Stops being one when

- They delete their SailingEvent for this event.
- The Event itself is canceled.
- They lose Boat Ownership of the boat (via co-owner removal).

## Examples

- **Bob fields "Wind Dancer" in the Wednesday Night Series.** He
  calls `PUT /api/events/{wednesday_evening}/sailing-event` with
  Wind Dancer's UUID. Bob is now Event Captain of Wind Dancer for
  Wednesday evening. He sets dock_time = 5:30pm, invites his usual
  crew pool, and toggles `accept_crew_requests=true` because he's
  short Bowman.
- **Bob and Carol are co-owners of Wind Dancer.** Either can be the
  Event Captain — the role is per-`BoatCrew(role='owner')`, not
  per-person. Whichever one calls upsert first creates the row;
  subsequent calls from either go to the same SailingEvent.

## Distinctions

- **Event Captain is scoped to one (event, boat) pair.** Bob is
  Captain of Wind Dancer for Wednesday Night Series race 4; he is
  not Captain of any other boat or any other race unless he files
  separate SailingEvents.
- **Event Captain is not `event_manager`.** Event Manager is a
  system role administering the underlying Event/Regatta; Event
  Captain is a relational role on the per-boat plan.
- **Crew is not a Captain.** Crew members on a SailingEvent are
  represented by EventCrew rows, not SailingEvent rows. They have
  no Captain authority.

## Technical anchor

- **Predicate**: `SailingEvent.boat_uuid = B AND BoatCrew(boat_uuid=B,
  person_uuid=P, role='owner', status='active')`
- **Enforced by**: `PUT /api/events/{event_id}/sailing-event` —
  caller-scoping joins through `BoatCrew(role='owner', status='active')`.
- **Related domain**: `role::relational::boat_owner`,
  `resource::concorda::sailing_event`, `resource::concorda::event_crew`.
