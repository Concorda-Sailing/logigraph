---
node_id: rule::crew_visibility::peer_pii_resume_gated
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-09
last_reviewed_against_hash: 9ebfaa367ee7dae1704435eb70cc714c30d6bd8b06c64c86e7716ade2158488b
fan_out: 3
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

The rule is currently implemented in **three surfaces** (fan_out=3):

- **Backend events endpoint** (`enforces`,
  `concorda-api/routers/events.py`): The function
  `_event_crew_to_read` (events.py:2235–2406) computes
  `resume_published` from `(person.preferences or {}).get("crewfinder",
  {}).get("opt_in", False)` and applies an `include_pii` decision based
  on `viewer_is_owner or viewer_is_self or resume_published`. PII
  fields are null-masked when `include_pii` is false. Called from
  `GET /api/events/{event_id}/sailing-event/crew`. **Known
  duplication**: the same `resume_published` predicate appears
  inline at events.py:2235 and again at :2400 — the helper has not
  been extracted yet.
- **Backend boats endpoint** (`enforces`,
  `concorda-api/routers/boats.py:292–334`): The endpoint
  `GET /api/boats/{boat_id}/crew/visible` filters crew rows by the
  same `preferences.crewfinder.opt_in` predicate but uses boolean
  filtering (omits non-visible rows) rather than null-masking.
  Different response shape from the events endpoint.
- **Frontend defensive mirror** (`displays`,
  `concorda-web/src/app/members/schedule/[id]/page.tsx:953`):
  `const visible = ec.resume_published === true;` gates whether the
  rendered crew row shows contact info or initials-only avatar. The
  backend has already filtered — this is intentional defense in
  depth. Removing it would not produce an immediate leak but would
  remove the second line of defense and the legibility of the rule
  in the component code.

A unified `services/visibility.py::has_published_resume(person)`
helper would consolidate the two backend predicates and the frontend
mirror. Phase 4 refactor target.

## Open questions

- Should the events endpoint and the boats `/crew/visible` endpoint
  return the same response shape (null-mask vs. boolean filter)?
  They implement the same rule but produce different payloads, which
  forces frontend code to handle both.
- Should the frontend defensive gate be made universal (every crew
  rendering site) or removed once the API is judged sufficiently
  trustworthy? Current position: keep, because the defense is cheap
  and the legibility is valuable.
- If "publishing a resume" and "wanting to be reachable" diverge in
  the future (e.g., resume becomes a fuller profile and visibility
  becomes a separate toggle), this rule's `attribute::resume_published`
  reference will need to be split.
