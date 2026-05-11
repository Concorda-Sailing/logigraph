---
node_id: rule::datetime::utc_aware_storage_and_org_tz_display
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: 692694c3794270f9ed59522eb5770fe9fdd424a8343d759fdcafaecd7bdcd120
fan_out: 5
---

# Datetimes are UTC-aware at rest, org-tz at the surface

## The rule

Concorda's datetime handling has three layers, each with a strict
convention.

**Storage layer (Python / SQLAlchemy).** Every datetime column on
every model uses the custom `UtcDateTime` SQLAlchemy type, not the
built-in `DateTime`. `UtcDateTime` stores naive-as-UTC on disk
(SQLite has no timezone type) and returns *aware* datetimes on read.
The application code receives a `datetime` with `tzinfo=UTC` and can
do arithmetic safely.

**Wire layer (API ↔ Web).** Datetimes cross the wire as ISO-8601
strings in UTC, with a `Z` or `+00:00` suffix. Both sides of the
boundary assume UTC unless the suffix says otherwise.

**Display + input layer (Web).** The browser is in some random
timezone. The user wants to see times in the *organization's*
timezone (set on `OrgConfig.tz`), not the browser's. Three helpers
in `concorda-web/src/lib/datetime.ts` are the *only* approved way to
cross this boundary:

- `formatInOrgTz(isoString, format)` — UTC ISO string → formatted
  string in the org's timezone.
- `ymdInOrgTz(isoString)` — UTC ISO string → date-only `YYYY-MM-DD`
  in the org's timezone.
- `orgInputToUtcIso(localInputValue)` — value from a
  `<input type="datetime-local">` interpreted as a wall-clock in the
  org's timezone → UTC ISO string for save.
- `utcIsoToOrgInput(isoString)` — inverse: UTC ISO → local-input
  string in the org's timezone, used to populate
  `<input type="datetime-local">` value on edit forms.

Direct calls to `Date.getHours()`, `Date.toLocaleString()` (without an
explicit `timeZone` option), `new Date().toISOString().slice(0, 10)`,
or similar are **forbidden** in production code. They silently
compute against the *browser's* timezone, which is whatever the
user's laptop says — not the organization's.

## Why it exists

The convention is mandatory because of two prior incidents and an
ongoing audit:

- **Pre-2026-05-06 calendar imports** were stored with the assumption
  that "naive datetime = local time" — but the local time was
  ambiguous (sometimes the importing host's TZ, sometimes Boston, in
  one case UTC-treated-as-local). The result was ~4–5h drift on
  imported events, surfacing as "the regatta says 5:30pm but the
  Notice of Race says 5:30pm" not matching reality.
- The **2026-05-07 component audit** found ~30 frontend components
  using `Date.getMonth()`, `.toLocaleString()` without `timeZone`,
  and similar shortcuts. Each was correct in the developer's
  browser timezone and quietly wrong in any other.

The fix layered the conventions: `UtcDateTime` enforces the storage
guarantee, the wire is UTC-only by contract, and the org-tz helpers
are the *single* boundary where the browser's timezone is allowed to
influence anything (and even there, the *org's* timezone is what
matters, not the browser's — the helpers take an explicit
`timeZone` argument under the hood).

## Examples

- **Stored**: `Event.start_at` is `2026-05-15T21:30:00+00:00` (a
  UTC-aware datetime).
- **Wire**: serialized as `"2026-05-15T21:30:00Z"` in the JSON
  response.
- **Display (Boston org)**: `formatInOrgTz(start_at, "h:mma")` →
  `"5:30pm"` (UTC-4 EDT).
- **Display (LA org)**: same input → `"2:30pm"` (UTC-7 PDT).
- **Edit (Boston org, user in Tokyo)**: edit form pre-populates the
  `<input type="datetime-local">` with the Boston-local
  `2026-05-15T17:30` via `utcIsoToOrgInput`. User changes it to
  `17:45`. On save, `orgInputToUtcIso` reads "5:45pm in Boston" and
  produces `2026-05-15T21:45:00Z`. The user's browser-in-Tokyo
  timezone is never involved.
- **Forbidden equivalent**: `new Date(start_at).getHours()` returns
  17 in Tokyo, 21 in UTC, 14 in LA — depending on whose laptop. Use
  the helpers.

## Counter-examples (what the rule does NOT do)

- It does **not** require all *display strings* to go through the
  helpers. Static text ("Spring 2026 regatta") doesn't need
  formatting. The rule fires when a datetime value is being
  rendered or parsed.
- It does **not** apply to wall-clock-only durations. "30 minutes
  before start" is a duration arithmetic, not a timezone conversion;
  do it in milliseconds.
- It does **not** mean "always use the user's browser timezone."
  Concorda explicitly prefers the *organization's* timezone for
  display. A Boston yacht club's regatta is displayed in Boston
  time to a member traveling in Tokyo. That is intentional.

## Decision table

| Operation | Approved helper / type | Forbidden shortcut |
|-----------|------------------------|---------------------|
| Define a datetime column                 | `UtcDateTime`             | built-in `DateTime` |
| Format a stored UTC datetime for display | `formatInOrgTz`           | `Date.toLocaleString()` without `timeZone` |
| Get a date-only `YYYY-MM-DD` for display | `ymdInOrgTz`              | `new Date(...).toISOString().slice(0, 10)` |
| Parse `<input type="datetime-local">` for save | `orgInputToUtcIso`  | `new Date(inputValue).toISOString()` |
| Populate `<input type="datetime-local">` on edit | `utcIsoToOrgInput` | `new Date(iso).toLocaleString("sv-SE")` and string-trimming |
| Compute "today" for filtering            | `ymdInOrgTz(new Date().toISOString())` | `new Date().toISOString().slice(0, 10)` (gives UTC date, not org date) |
| Server-side arithmetic on stored times   | UTC-aware Python datetimes | naive datetimes |

Every line crossing storage ↔ wire ↔ display ↔ input must use the
approved helper. The audit finds drift wherever a line was crossed
without one.

## Surfaces

- **Storage**: `concorda-api/utils/utc_datetime.py::UtcDateTime` (the
  custom SQLAlchemy type), applied on every datetime column in
  `concorda-api/models/`. Reference model: `models/event.py::Event`.
- **Display helpers** (frontend, `concorda-web/src/lib/datetime.ts`):
  - `formatInOrgTz` (70+ dependents)
  - `ymdInOrgTz` (35+ dependents)
  - `partsInTz` (lower-level utility used by the others)
- **Input helpers** (same file):
  - `orgInputToUtcIso` (13 form-save sites)
  - `utcIsoToOrgInput` (form-populate counterpart)
  - `orgDateInputToUtcIso`, `utcIsoToOrgDateInput` (date-only
    siblings for `<input type="date">`)
- **OrgConfig**: `OrgConfig.tz` is the timezone string consumed by
  the helpers (e.g. `"America/New_York"`).

## Gotchas

- **`toLocaleString()` *with* an explicit `timeZone` option is fine
  in principle**, but the right answer is still to call the helper
  — keep the timezone-string lookup centralized in
  `datetime.ts` so a future TZ rename or DST quirk lands in one
  place.
- **Pre-2026-05-06 imports are still drifted.** The audit memory
  flags that historical rows may be 4–5h off from where the user
  intends. New imports go through the helpers; old ones are fixed
  by hand. Don't write a "blanket fix" script without per-event
  inspection.
- **`<input type="datetime-local">` does not carry a timezone.** Its
  value is a wall-clock string. `new Date(value).toISOString()`
  interprets it as the browser's local time, which is wrong. The
  helper interprets it as the *org's* local time, which is right.
- **Server-side date math should stay on aware datetimes.** Once
  `UtcDateTime` returns an aware value, don't downgrade it to naive
  ("strip the tz to avoid the warning"). Arithmetic on aware
  datetimes is safe; arithmetic mixing naive and aware raises.
- **Don't sprinkle TZ logic into components.** The rule prevents
  helpers from being re-implemented inline. If a component needs a
  new format the helpers don't expose, *extend the helpers*, don't
  drop down to raw `Date`.

## Technical anchor

- **Storage type**: `concorda-api/utils/utc_datetime.py::UtcDateTime`
  (not depgraph-tracked; referenced by model columns).
- **Reference model**: `concorda-api/models/event.py::Event` —
  `start_at`, `end_at`, `created_at`, `updated_at` all `UtcDateTime`.
- **Display + input library**: `concorda-web/src/lib/datetime.ts` —
  every helper used at the boundary.
- **Adjacent memory**: `feedback_naive_datetime_convention.md`,
  `feedback_timezone_helpers_mandatory.md` — the user-facing
  conventions; this rule formalizes them.
- **Adjacent domain**: `resource::concorda::event`,
  `resource::concorda::organization`.
