---
node_id: rule::schedule::canonical_listing
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-10
last_reviewed_against_hash: a56f93e5065ea58ca436fd1c8a7ff1e14f3099f00db6b7f6b11003ba6b1649de
fan_out: 4
---

# my-schedule is the canonical schedule endpoint; others are scope-narrowed views

## The rule

A user's schedule has one **canonical** answer:
`GET /api/events/my-schedule`. It aggregates the five sources of
"things on my plate":

1. Personal events (Event.category=personal, owner_id=me)
2. Bookmarked events (PersonEvent rows linking me to public events)
3. Registered events (EventRegistration with status=Confirmed)
4. Crew assignments (EventCrew rows where I'm in the crew)
5. Co-owned boats' events (SailingEvent on a boat I co-own)

Each row is built via the **shared helper**
`_build_schedule_item_for_event` in `routers/events.py`. This helper
is the canonical shape of a schedule row.

Other endpoints that surface schedule-shaped data are
**scope-narrowed views or format conversions**, not parallel
implementations:

- `GET /api/profile/event-registrations` returns only source #3.
- `GET /api/events/{id}/detail` returns one row using the same helper
  (added 2026-05-09 commit `1b5d864` to break the frontend's
  dependency on `my-schedule` for single-event refreshes).
- `GET /api/schedule/feed/{token}.ics` returns the same scope as
  `my-schedule` serialized as ICS.

If you find yourself building a fifth surface that selects events on
behalf of a user, route it through `_build_schedule_item_for_event`
and explain in the rule which scope subset you cover.

## Why it exists

The schedule was thrashing. Two recent revert/re-revert pairs
(`7570175 fix(schedule): always include user-owned personal events` →
`57f2e00 Revert` → `b887b73 test(schedule): pin co-owner visibility
rules`) and the recent `1b5d864 fix(schedule): detail page calls
/api/events/{id}/detail, drops mySchedule coupling` are downstream of
not having a clear rule about what counts as "my schedule" and which
endpoint is the source of truth.

This rule names `my-schedule` as canonical so that:

- Any future "show me schedule-shaped data" requirement starts with
  "what subset of my-schedule's scope?" rather than "should I write
  a new endpoint?"
- Frontend code knows that `eventsApi.mySchedule()` and
  `eventsApi.getDetail(id)` produce row-shaped objects compatible
  with each other (same helper underneath).
- Diverging schedule logic across surfaces is now an explicit rule
  violation, not a quiet inconsistency.

## Examples

- **Frontend wants the schedule list view.** Calls
  `eventsApi.mySchedule()`. Gets aggregated events from all 5
  sources, ranked by date.
- **Frontend wants to refresh one event after an action.** Calls
  `eventsApi.getDetail(eventId)`. Gets the same `ScheduleItem` shape,
  built by the same helper, no need to refetch the whole schedule.
- **Calendar app subscribes to ICS feed.** Calls
  `/api/schedule/feed/{token}.ics`. Gets the same scope as
  `my-schedule`, formatted as iCalendar.
- **Profile page wants registrations only.** Calls
  `/api/profile/event-registrations`. Gets a registrations-narrowed
  subset of source #3.

## Counter-examples (what the rule does NOT do)

- The rule does **not** enforce that all schedule-shaped data goes
  through a single SQL query. The helper exists; the aggregating
  query in `my-schedule` is its own.
- The rule does **not** apply to admin / org-wide listings (those
  are not "my schedule" — they're someone else's plate).
- The rule does **not** prevent narrower endpoints from existing.
  `event-registrations` is a legitimate narrowed view; the rule
  asks that it stay a narrowed *subset*, not a parallel implementation.

## Decision table

| Caller wants                             | Use                                                   |
|------------------------------------------|-------------------------------------------------------|
| Full schedule list                       | `GET /api/events/my-schedule`                         |
| Refresh single event after action        | `GET /api/events/{id}/detail`                         |
| Just registrations                       | `GET /api/profile/event-registrations`                |
| Calendar subscription (ICS)              | `GET /api/schedule/feed/{token}.ics`                  |
| New schedule-shaped surface              | Use `_build_schedule_item_for_event`; document scope subset in this rule |

## Edge cases

- **Personal events with `date < today`**: must still appear in
  `my-schedule` (the user owns them, even if past). This was the
  bug behind the revert/re-revert sequence. Date filtering is
  scoped per-source.
- **Co-owned boats' events**: appear via the SailingEvent → Boat →
  BoatCrew(role=owner) join. Adding a co-owner mid-event makes
  their `my-schedule` reflect the event going forward.
- **Bookmarked + registered + crew on same event**: deduped by event
  ID — the user sees one row regardless of how many claims they
  have on the event.

## Surfaces

- **Canonical aggregator** (`enforces`,
  `routers/events.py::get_my_schedule`): the primary five-source
  aggregator. `_build_schedule_item_for_event` is the row-shaping
  helper; lives in the same file.
- **Single-event consumer** (`checks`,
  `routers/events.py::get_event_detail`): added 2026-05-09 to let
  the detail page refresh one event without re-fetching the full
  schedule. Uses the same helper.
- **Registrations-narrowed view** (`checks`,
  `routers/profile.py::get_my_event_registrations`): scope subset.
  `medium` confidence on the claim because the row shape isn't
  identical to my-schedule's (different fields).
- **ICS export** (`serializes`,
  `routers/calendar.py::get_calendar_feed` / route at
  `/api/schedule/feed/{token}.ics`): same scope, ICS format.

## Open questions

- **Should `event-registrations` route through
  `_build_schedule_item_for_event`?** Currently it has its own row
  shape. Migrating would unify but might break existing callers
  expecting registration-specific fields.
- **Should there be a `_schedule_sources` enum** so callers of
  `my-schedule` can request a subset (e.g., `?sources=crew,coowned`)?
  Better than building parallel narrowed endpoints. Punt until a
  third use case appears.
- **Calendar feed deduplication is independent of my-schedule's
  dedup.** Verify they stay aligned; potential drift if scope diverges.
