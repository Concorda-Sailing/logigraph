---
node_id: rule::events::personal_event_excluded_from_public_listings
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: dfb7778a1e86eb525f36967dfd78fb566e17ed9efa685a2493946604dd3f3d98
fan_out: 5
---

# Personal events are excluded from public listings

## The rule

An `Event` whose `category` is `'personal'` represents a private item
on one Person's calendar (a doctor's appointment, a vacation block,
"can't sail Tuesday"). Personal events are intentionally invisible to
everyone except their owner.

Two invariants must hold across the codebase:

1. **Listing filter**: every endpoint that returns a list of Events
   to anyone other than the owner must include
   `Event.category != 'personal'` in its query. Missing the filter
   leaks calendar rows into public listings.
2. **Slug nullity**: a personal Event must have `slug = None` (SQL
   NULL), never the empty string `''`. The empty string collides with
   the UNIQUE constraint on `events.slug` and the second personal
   event a user creates blows up the insert.

Personal events surface to their owner via two paths only:
`GET /api/events/personal` (dedicated listing, viewer-scoped) and
`GET /api/events/my-schedule` (which includes the caller's own
personal events alongside their bookmarked/registered public
events).

## Why it exists

Personal events were added so members could block time on their own
calendar without that block showing up to other members. The flow
relies on two pieces:

- **Category enum** (`personal` is one value, `regatta` / `social` /
  etc. are others). The filter is a category-based exclusion, not a
  visibility flag — there's no `Event.is_public` column.
- **Slug uniqueness**: slugs are URL identifiers. Public events get
  human-readable slugs (`spring-regatta-2026`). Personal events have
  no public URL, so they get `slug = None`. SQLite's UNIQUE
  constraint allows multiple NULLs but rejects multiple `''`. If a
  code path writes `slug=''` for personal events, the second insert
  raises an IntegrityError.

This rule has a regression history that justifies elevating it to a
formal rule rather than a comment:

- **Commit `4fd165d`** fixed the slug-UNIQUE collision by switching
  personal-event slug writes from `''` to `None` in `Event.__init__`.
- **Commit `7570175`** regressed the listing filter — the main
  `/api/events` query stopped excluding personal events. Caught
  pre-prod.
- **Commit `57f2e00`** reverted `7570175`.
- **Commit `b887b73`** re-applied the date-floor fix from `7570175`
  while preserving the category filter. The regression vector is
  "change a public listing query and forget to re-include the
  category exclusion."

## Examples

- **Carol creates a personal event "Vacation" for next week.** She
  POSTs to a personal-event creation endpoint. The Event row is
  inserted with `category='personal'`, `slug=None`, `owner_id=Carol`.
- **Bob calls `GET /api/events`.** The query excludes
  `category='personal'`. Bob does not see Carol's vacation.
- **Carol calls `GET /api/events/my-schedule`.** The query includes
  her registered/bookmarked events *and* her personal events. She
  sees her vacation.
- **Carol calls `GET /api/events/{vacation_id}`.** Endpoint sees
  `category='personal'`, checks `owner_id == current_user_id`, allows
  the read.
- **Bob tries `GET /api/events/{vacation_id}` directly via guessed
  id.** Endpoint denies (404 or 403) because category is personal
  and Bob isn't the owner.

## Counter-examples (what the rule does NOT do)

- The rule does **not** hide a public event from a non-registrant.
  Public events (`category != 'personal'`) appear in listings to
  every authenticated user regardless of registration status.
- The rule does **not** apply to events owned by an Organization
  (those have `organization_id` set and `category != 'personal'`).
  Visibility for org events follows Tier-C scoping
  (`rule::auth::tier_c_org_scope_chokepoint`).
- The rule does **not** forbid personal events from having a slug.
  It forbids the slug being `''`. `None` is required.

## Decision table

| `Event.category` | `Event.slug`     | Caller is `owner_id`? | Outcome on list endpoint    | Outcome on single-event read |
|------------------|------------------|------------------------|------------------------------|------------------------------|
| `personal`       | NULL             | Yes                    | Shown in `/events/personal`, `/events/my-schedule` | Read allowed |
| `personal`       | NULL             | No                     | Hidden from all listings     | 404 / 403                    |
| `personal`       | `''`             | any                    | **Insertion fails** — UNIQUE collision on second personal event |
| `regatta` / `social` / etc. | non-empty | any           | Shown in public listings (subject to other filters) | Read allowed (subject to other gates) |

The category filter must be present in every public listing query.
The slug-NULL invariant must hold at insert time.

## Surfaces

- **Public listings that must filter `category != 'personal'`**:
  - `GET /api/events` (events.py:111)
  - `GET /api/events/upcoming` (events.py:134)
  - `GET /api/events/registration-counts` (events.py:730)
  - `GET /api/events/{0}/detail` (events.py:845 — scoped path)
- **Owner-scoped listing that *includes* personal events**:
  - `GET /api/events/personal` — viewer-scoped to `current_user.id`
  - `GET /api/events/my-schedule` — includes caller's personal events
- **Single-event reads that must check ownership for personal**:
  - `GET /api/events/{id}` — category check + owner check
- **Slug-NULL invariant**:
  - `Event.__init__` — personal events normalize `slug=None`
  - any other code path that constructs personal events (importers,
    seed scripts) must use `None`, not `''`.

## Gotchas

- **The most common bug is omitting the filter on a *new* listing
  endpoint.** Whenever you add a `GET` that returns events, ask:
  "should this include personal events?" Default answer: no.
- **Don't write `slug=''` "to satisfy the not-null constraint."** The
  column allows NULL; the constraint allows multiple NULLs. Writing
  `''` will pass the first time and explode the second time.
- **`category` is a free-form string today, not an enum.** A typo
  (`'pesonal'`) skips the filter silently. Use the constant defined
  on the Event model rather than hand-typing the string.
- **`my-schedule` is the one exception to the filter rule** because
  the viewer *is* the owner of any personal events it returns. New
  schedule-shaped endpoints should mirror this exactly: include
  personal events *only* where `owner_id = current_user.id`.

## Technical anchor

- **Category constant**: `concorda-api/models/event.py::Event.CATEGORY_PERSONAL` (use this, not the literal string).
- **Slug normalization**: `Event.__init__` — sets `slug = None` when category is personal.
- **History anchor commits**: `4fd165d` (slug fix), `7570175` → `57f2e00` → `b887b73` (filter regression cycle).
- **Adjacent ontology**: `resource::concorda::event`, `role::system::member`.
