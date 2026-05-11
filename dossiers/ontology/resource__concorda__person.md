---
node_id: resource::concorda::person
node_kind: ontology
subkind: resource
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: d5f9f598fd1bacff82afca7dad3a8c878fe048e3c832dd97683f013ac69d3d64
---

# Person

## What it is

A row in the `persons` table representing one human. Every authenticated
action in Concorda happens *as* a Person; every relationship (crew,
ownership, registration, approval) keys on `person_uuid`. A Person is
created by `POST /api/auth/register`, by admin import, or by accepting
an emailed invitation that resolves to a fresh account.

A Person is distinct from a `User` (which is a synonym in this codebase
— `User` is the SQLAlchemy class name for the same row) and from a
`Contact` (an admin-side contact-card for stewards/fleet captains,
which may or may not link to a Person via `Contact.person_uuid`).

## Key fields

- `email` — unique (case-insensitive on read), the login key.
- `password_hash` — bcrypt-hashed; `NULL` for accounts that signed up
  via invite and haven't set a password yet (drives the
  `AccountSetupToken` flow).
- `email_verified` — boolean; gated on for paid signups and some
  account actions. Per `project_free_signup_verification`, free signups
  require verification before auto-login.
- `first_name`, `last_name`, `phone_number`, `mailing_address`, `date_of_birth`,
  `picture_url`, `banner_url` — profile fields.
- `preferences` — JSON nested config: `directory` (opt-in + show flags),
  `crewfinder` (opt-in for resume publication), `notifications`,
  `my_schedule_filters`, `setup_wizard_completed`.
- `meta` — free-form JSON for additional metadata.
- `tos_accepted_at` — legacy mirror; canonical source is
  `PersonContractAcceptance`.

## Relationships

- **Has many** `UserRole` (system roles like `org_admin`, optionally org-scoped)
- **Has many** `BoatCrew` (crew/owner relationships to specific boats)
- **Has many** `PersonProduct` (memberships / entitlements)
- **Has many** `EventCrew` (crew slots on specific events)
- **Has many** `EventRegistration` (paid event signups)
- **Has many** `PersonContractAcceptance` (TOS/CoC/privacy acceptances)
- **Optionally referenced by** `Contact.person_uuid` (admin contact card)

## Visibility

PII (email, phone, mailing address, DOB, additional contacts) is
self-only by default. Exposed to peers only when the Person opts in:

- `preferences.directory.opt_in` exposes basic identity to the member
  directory; per-field show flags (`show_phone`, `show_email`) gate
  contact info.
- `preferences.crewfinder.opt_in` exposes the Person's `SailingResume`
  to the crewfinder browse surface (drives
  `rule::crew_visibility::peer_pii_resume_gated`).

Boat owners always see unfiltered crew PII on boats they own.

## Technical anchor

- **Model**: `concorda-api/models/person.py::Person` (aliased as `User`)
- **Read schema**: `concorda-api/schemas/profile.py::ProfileRead` (self-view, full PII)
- **Auth identity**: surfaced via `AuthUser` / `get_current_user_id`; the
  bearer token (`AuthToken` or `AgentToken`) resolves to a `person_uuid`.
- **Privacy rule**: `rule::crew_visibility::peer_pii_resume_gated` governs
  peer exposure on crew surfaces.
