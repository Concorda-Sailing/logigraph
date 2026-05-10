---
node_id: rule::crew_visibility::peer_pii_resume_gated
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-10
last_reviewed_against_hash: a03364b2b93fdf09058aa3b12639cc8ee85f4212f52d09f18cf03d13e0107837
fan_out: 5
---

# Peer crew identity hidden unless resume is published

## The rule

Crew members on a boat can see each other's *names* and *roles* in a
crew roster, but their personal contact info (email, phone, profile
picture) is hidden from peer crew unless that person has published a
sailing resume. Boat owners, co-owners, event managers, and admins
always see the unfiltered roster — they need full visibility to
coordinate.

The same rule applies on event-scoped crew listings (who's crewing
this race) and on boat-scoped crew listings (who's on this boat).
The two surfaces use different mechanisms (null-masking on the events
endpoint, boolean filtering on the boats endpoint) — see the
**Surfaces** section.

## Why it exists

Crew rosters surface identity to people you might not have met. The
default position is **privacy**: a crew member appears as a name in a
list, not a contact card. Sailors opt into being reachable by
**publishing a sailing resume**, which signals "I'm available to
crew, want to be invited to other boats, and consent to peers seeing
how to reach me."

Owners need full visibility regardless because their job is to
coordinate the crew — knowing how to reach a crew member to confirm
attendance, reschedule, or fill a last-minute gap is operationally
necessary.

The rule is enforced in *multiple places* by design — the backend is
the source of truth (it null-masks PII fields before the response
leaves the API) and the frontend has a defensive mirror that hides PII
in the rendered roster even when the backend already filtered. The
defensive frontend gate is intentional: it protects against API
regressions and makes the visibility intent legible in the
component code.

## Examples

- **Alice and Carol are both crew on Bob's boat.** Carol has not
  published a resume. Alice opens the schedule page for an upcoming
  race and views the crew roster. Alice sees Carol's name and crew
  role; she does not see Carol's email, phone, or profile picture.
- **Carol then publishes her sailing resume.** Alice refreshes the
  roster. Alice now sees Carol's email, phone, and profile picture.
- **Bob (the boat owner) views the same roster.** Bob sees Carol's
  full contact info regardless of whether Carol has published a
  resume.
- **Carol views her own row.** Carol always sees her own contact info
  (the rule never hides a person's data from themselves).
- **An event manager (Eve) reviewing a race roster across multiple
  boats.** Eve sees full contact info for every crew member regardless
  of resume status.

## Counter-examples (what the rule does NOT do)

- The rule does **not hide that a crew member exists.** Names and
  crew roles (main, alternate, status) are always visible to other
  crew on the same boat.
- The rule does **not apply to admins or event managers.** They see
  unfiltered rosters for coordination.
- The rule is **not** implemented as a peer-by-peer
  is-this-person-published check on the *consumer* side — the API
  applies the filter and returns either populated or null PII fields.
- The frontend gate at `schedule/[id]/page.tsx:953` is **not
  redundant.** It is an intentional defensive mirror that protects
  against API regressions. Removing it would not produce a leak today
  (the backend filters), but it would remove a legible
  in-component statement of intent and the second line of defense.

## Decision table

The structured form. Rows enumerate viewer/target/condition
combinations; the Outcome column states what the rule produces. Use
this for boundary reasoning — it's exhaustive over the cases the rule
covers.

| Viewer relationship    | Target          | resume_published | Outcome                               |
|------------------------|-----------------|------------------|---------------------------------------|
| Self                   | Self            | any              | Show all (own row, never gated)       |
| Boat owner             | Crew on same boat | any            | Show all (owner unfiltered)           |
| Co-owner               | Crew on same boat | any            | Show all (co-owner = owner)           |
| Event manager          | Any crew at event | any            | Show all (coordination role)          |
| Org admin / system admin | Any crew      | any              | Show all (admin)                      |
| Peer crew (same boat)  | Other peer      | true             | Show all (peer opted in via resume)   |
| Peer crew (same boat)  | Other peer      | false            | Hide PII (email, phone, picture)      |
| Non-crew, non-owner    | Any crew        | any              | 403 / no access (different rule)      |

**PII fields that get hidden**: `email`, `phone`, `picture_url`.
**Always shown**: `name`, `crew_role` (main/alternate), `status`
(invited/accepted/declined).

**Hide mechanism inconsistency** (known smell): the events endpoint
null-masks (returns the row with PII fields set to `null`), while
the boats `/crew/visible` endpoint boolean-filters (omits the row
entirely if visibility is false). Both implement the same rule;
the response shapes differ. Phase 4 refactor target.

## Edge cases

- **A peer who is also a co-owner of the same boat.** They count as
  Boat Owner for visibility purposes — full unfiltered view.
- **A person viewing their own row** in any roster. Always sees own
  PII; the rule explicitly does not gate self-view.
- **Resume published *after* the roster was rendered.** The next
  fetch reflects the new visibility — there is no caching of the
  visibility decision client-side.
- **The boats `/crew/visible` endpoint** filters by visibility
  *opt-in*, not by resume publication state directly. The two are
  the same field today (`preferences.crewfinder.opt_in`), but the
  semantics are subtly different: "I'm publishing my resume" implies
  "I want to be reachable." If those concepts ever diverge, this
  rule needs to specify which.
- **Event managers viewing a race that crosses multiple boats.**
  Their event-manager role grants unfiltered visibility across all
  boats in the event, not just one.

## Surfaces

As of 2026-05-10, the rule is implemented as **one canonical helper +
three callers + one frontend mirror**. The helper consolidation
landed when the previously-duplicated inline predicate was extracted
(see git history of `concorda-api/services/visibility.py`).

**Canonical helper** (`enforces`,
`concorda-api/services/visibility.py`):
- `has_published_resume(person) -> bool` — returns whether the
  person has opted into crewfinder visibility. Defensive against
  None / missing prefs / non-dict crewfinder structure.
- `peer_can_see_pii(viewer_is_owner, viewer_id, target_person_id,
  target_person) -> bool` — full peer-visibility decision implementing
  the decision table (self / owner / peer-with-resume / peer-without).
This module is the single source of truth. Any change to the rule
should land here.

**Callers consuming the helper** (`checks`):

- **Backend events endpoint** (`concorda-api/routers/events.py`):
  - `_event_crew_to_read` (events.py:2225) calls
    `has_published_resume(person)` for the `resume_published` field
    on every row.
  - `get_event_crew` (events.py:2380) calls
    `peer_can_see_pii(...)` to compute `include_pii` per row, then
    null-masks PII fields when false.
- **Backend boats endpoint**
  (`concorda-api/routers/boats.py:294–329`,
  `GET /api/boats/{boat_id}/crew/visible`): calls
  `has_published_resume(person)` to filter rows. Uses **boolean
  filtering** (omits non-visible rows) rather than null-masking.
  Same predicate, different response shape — see Open Questions.

**Frontend defensive mirror** (`displays`):

- `concorda-web/src/app/members/schedule/[id]/page.tsx:953` —
  `const visible = ec.resume_published === true;` gates whether the
  rendered crew row shows contact info or initials-only avatar. The
  backend has already filtered — this is intentional defense in
  depth. Removing it would not produce an immediate leak but would
  remove the second line of defense and the legibility of the rule
  in the component code.

**Surfaces NOT yet covered** (suspected gap, surfaced by the schedule
review of 2026-05-10):

- `concorda-api/routers/profile.py::get_my_crew`
  (`event_invitations` field, around line 596) returns
  `invited_by_name` to the invitee with no `has_published_resume`
  check on the inviter. This is the inverse direction (inviter → invitee)
  not covered by the current rule statement; needs decision on whether
  inviter names should also be opt-in gated.
- `concorda-api/routers/events.py::list_inbox_crew_requests`
  (around line 3035) returns the requester's full name + picture
  + reply_to email to the boat owner. This is the inverse-of-peer
  direction (owner sees requester); likely intentional to let owners
  identify who's asking, but undocumented as an exception to the
  rule.

## Open questions

- ✅ **Resolved 2026-05-10**: The previously-inline `resume_published`
  predicate was duplicated three times. Now consolidated into
  `services/visibility.py::has_published_resume`. All three callers
  go through the helper.

- **Still open**: Should the events endpoint and the boats
  `/crew/visible` endpoint return the same response shape
  (null-mask vs. boolean filter)? They both consume the helper
  correctly now, but the response shapes still differ: events emits
  rows with PII fields nulled; boats omits non-visible rows entirely.
  Frontend code has to handle both. Refactor candidate.

- **Still open**: Should the frontend defensive gate be made
  universal (every crew rendering site) or removed once the API is
  judged sufficiently trustworthy? Current position: keep, because
  the defense is cheap and the legibility is valuable.

- **Still open**: Should `inviter → invitee` PII be opt-in gated?
  `profile.py::get_my_crew` currently returns `invited_by_name`
  without checking the inviter's resume publication status. The
  current rule statement covers `peer crew → peer crew` but not the
  invitation direction. Needs explicit decision: extend the rule to
  cover inviter visibility, or carve out an exception for invitations.

- **Still open**: Should `owner → requester` PII be explicitly
  documented as exempt? `events.py::list_inbox_crew_requests` returns
  the requester's full name + picture + reply_to to the boat owner.
  Likely intentional (owner needs to identify who's asking) but
  currently undocumented in the rule.

- **Still open**: If "publishing a resume" and "wanting to be
  reachable" diverge in the future (e.g., resume becomes a fuller
  profile and visibility becomes a separate toggle), this rule's
  `attribute::resume_published` reference will need to be split.
