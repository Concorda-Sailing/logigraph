---
node_id: attribute::resume::published
node_kind: ontology
subkind: attribute
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 161775ad254255981ced70579609cf056ccfeaf378346905d521347aa78eb92f
---

# resume_published

## What it is

A derived boolean attribute on a Person: true iff they have opted in
to the crewfinder via `preferences.crewfinder.opt_in == True`. This is
the canonical "is this person's resume browseable" signal.

**Common mistake**: this is NOT computed from the existence of a
`SailingResume` row. A Person can have a populated SailingResume but
not be published (because they haven't ticked the opt-in box). Per
`rule::crew_visibility::peer_pii_resume_gated`, peer PII gating reads
this attribute, not the existence of a resume row.

## Predicate

```python
person.preferences.get("crewfinder", {}).get("opt_in", False) is True
```

## Why it matters

Gates peer-side PII visibility across crew surfaces:

- `_event_crew_to_read(include_pii=...)` reads this attribute to
  decide whether to mask `person_first_name`, `person_last_name`,
  `person_picture_url`, `person_email` on EventCrew rows.
- `routers/boats.py::list_visible_crew` filters crew rows where the
  target hasn't published.
- The crewfinder browse endpoint (`GET /api/crewfinder/*`) restricts
  to opted-in resumes.

It does **not** gate:
- Owner-side reads — owners always see their own crew unfiltered.
- The Person's own self-view of their resume.
- Public profile/directory presence (that's `preferences.directory.opt_in`).

## Lifecycle

Flips on when:
- The Person ticks the "publish to crewfinder" checkbox, which writes
  `preferences.crewfinder.opt_in = True` via `PUT /api/profile`.

Flips off when:
- They untick the box.
- An admin (rarely) flips it via the admin user-edit endpoint.

## Technical anchor

- **Canonical helper**: `concorda-api/services/visibility.py::has_published_resume`
- **Composite check**: `services/visibility.py::peer_can_see_pii` —
  combines ownership status, self-id, and this attribute.
- **Wire field**: `EventCrewRead.resume_published` boolean.
- **Related rule**: `rule::crew_visibility::peer_pii_resume_gated`.
