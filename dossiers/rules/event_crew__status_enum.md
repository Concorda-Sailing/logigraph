---
node_id: rule::event_crew::status_enum
node_kind: rule
definition_status: human_reviewed
last_reviewed: 2026-05-10
last_reviewed_against_hash: 0a05ff111aec7a7f5f737baecc1bc1591746f26668e55b12b5fc938c725f8dfd
fan_out: 7
---

# EventCrew status is one of six canonical values

## The rule

`EventCrew.status` is canonically one of six values:

```
pool, invited, accepted, declined, confirmed, requested
```

The source of truth is `EventCrewStatus(str, Enum)` in
`concorda-api/models/event_crew.py`. New code that writes status must
reference enum members (`EventCrewStatus.INVITED`, etc.) so typos
become `AttributeError` instead of silently landing in the database.
Pydantic types `EventCrewRead.status` as the enum, so response
payloads are validated — a row with a value outside the canonical set
raises a validation error rather than shipping.

The DB column remains `String(20)` for backwards compatibility with
existing rows; tightening to a CHECK constraint is a follow-up
requiring a migration.

## Why it exists

Before this rule (commit `dd72f2f`, 2026-05-10) the status field was
referenced ~80 times across `routers/events.py`, services, and tests
as a bare string literal. The model column comment listed 4 values
while the runtime used 6. There was no enum to import from, no
validation on responses, and a typo at any write site would land in
the DB silently.

This rule makes the enum the canonical reference and gives consumers
something to import. It's the type-safety layer the codebase was
missing on this particular field.

## Examples

- `ec.status = EventCrewStatus.ACCEPTED` — correct write.
- `if ec.status == EventCrewStatus.INVITED:` — correct read against
  the enum (works because of `(str, Enum)` mixin; `==` compares the
  underlying string).
- `if ec.status == "invited":` — also correct (legacy string-literal
  comparison still works for the same reason). Acceptable in
  existing code; new code should prefer the enum.

## Counter-examples (what the rule does NOT do)

- The rule does **not** enforce state transitions. Going from
  `confirmed` directly back to `invited` is structurally allowed by
  the type system; it's the *caller's* responsibility to use only
  legal transitions. State-machine validation is a separate concern
  and a candidate for a future rule.
- The rule does **not** prevent legacy string literals in reads
  (filters, comparisons). They still work because of `(str, Enum)`;
  cleanup is incremental.
- The rule does **not** apply to `BoatCrew.status`. That's a
  different field with its own enum (`active`, `prospective`,
  `invited`, `declined`) which currently has no canonical enum
  class. Pending separate rule.

## Decision table

The six canonical states, what they mean, who creates them, and where
they can transition to:

| State       | Meaning                                                  | Set by                                                       | Valid next states              |
|-------------|----------------------------------------------------------|--------------------------------------------------------------|--------------------------------|
| `pool`      | Owner has marked candidate; no invite sent yet.          | `set_crew_pool` (PUT crew-pool)                              | invited, accepted (rare self), declined (rare) |
| `invited`   | Owner sent invite; awaiting response.                    | `send_crew_invites` (POST crew-invite); `evaluate_roster` (alt promotion) | accepted, declined             |
| `accepted`  | Crew member accepted invite; not yet confirmed.          | `respond_to_event_crew` (PUT crew-respond); `mark_event_crew_response` (PUT crew-mark-response); `request_to_crew` accept | confirmed (via crew-confirm)   |
| `declined`  | Crew member declined.                                    | `respond_to_event_crew`; `mark_event_crew_response`; `request_to_crew` decline | (terminal)                     |
| `confirmed` | Owner has finalized crew. Notification sent.             | `confirm_event_crew` (POST crew-confirm)                     | (terminal-ish; rarely reverted) |
| `requested` | Sailor self-nominated; awaiting owner response.          | `request_to_crew` (POST crew-request)                        | accepted, declined             |

**Important asymmetry**: `accepted` from a `requested` row also
creates a `BoatCrew` row (the requester becomes a member of the boat
beyond the single event). `accepted` from an `invited` row does NOT
create a BoatCrew row — they're already crew or are crew for this
event only. See `events.py:respond_to_crew_request` and
`services/invite_dispatch.py::_EventCrewHandler.respond`.

## Edge cases

- **Owner self-invite**: when a boat owner sends invites and the
  owner is in the pool, their row auto-transitions to `accepted`
  rather than `invited` (no notification to self). See
  `services/crew_roster.py::notify_crew`.
- **Alternate promotion**: when a `main` crew member declines and
  open slots exist, `evaluate_roster` promotes the next `alternate`
  to `main` and (if their status was `pool`) transitions them to
  `invited`. See `services/crew_roster.py:evaluate_roster`.
- **`responded_by_uuid` ambiguity**: this field is set whenever
  status moves to `accepted` or `declined`, but is conflated between
  "the responder" (crew self-response) and "the recorder" (owner
  marking out-of-band). Documented as open question on
  `rule::crew_visibility::peer_pii_resume_gated`.

## Surfaces

- **Canonical definition** (`enforces`,
  `concorda-api/models/event_crew.py`): the `EventCrewStatus(str,
  Enum)` class.
- **Response validation** (`enforces`,
  `concorda-api/schemas/event_crew.py`): `EventCrewRead.status` is
  typed as the enum; FastAPI/Pydantic validates outgoing payloads.
- **Writers** (`checks`, in `events.py` and services): five primary
  endpoints + the dispatch services. See `claims_code` on the node
  JSON for the current list with line ranges.
- **Frontend mirror** (TS Literal union,
  `concorda-web/src/lib/api.ts`): `EventCrewStatus` and
  `EventCrewRole` are exported as Literal unions for type-safe
  consumption in the UI.

## Open questions

- Should the column tighten to a SQLAlchemy `Enum` type or CHECK
  constraint? Requires migration; deferred.
- Should reads (filters, comparisons) be migrated en masse to enum
  members for consistency, or left as string literals indefinitely?
  Current position: leave as-is until a code-quality pass; both work.
- Should there be a separate `rule::event_crew::state_machine` rule
  capturing the legal transitions in code (so an illegal transition
  fails at the call site, not just the DB)? Probably yes, eventually.
  This rule is about valid VALUES; that one would be about valid
  TRANSITIONS.
