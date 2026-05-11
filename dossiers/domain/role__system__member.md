---
node_id: role::system::member
node_kind: domain
subkind: role
definition_status: human_reviewed
last_reviewed: 2026-05-11
last_reviewed_against_hash: e4a380ec304f782e07a657e682597ea16734513370d574732cfa2bfb843ade9d
---

# Member

## Plain definition

A Member is any registered, authenticated Person. There is no
`UserRole` row required — being a Member is the default state for
anyone with an account. Every other system role is *additive* on top of
Member: an `org_admin` is also a Member, a `system_admin` is also a
Member.

## They can

- Sign in and sign out.
- Read and edit their own `Person` profile.
- Read and edit their own `SailingResume`.
- Bookmark / unbookmark events on their `my-schedule`.
- Register for events they are eligible for (paid or free).
- Accept or decline crew invites sent to them.
- Send crew requests for boats accepting crew on a given race.
- Browse the member directory (rows where the target person has opted in).
- Browse the boat finder (rows where the boat's resume is published).
- Browse the crew finder (rows where the person has opted in via `crewfinder`).

## They cannot

- Edit any other Person's profile.
- Create regattas, series, or system-level products.
- Modify any organization-level configuration.
- Bypass payment for paid registrations.
- Read PII of peers who haven't opted in (gated by
  `rule::crew_visibility::peer_pii_resume_gated`).

## Becomes one when

- A Person row exists for them in the `persons` table — there is no
  explicit grant. Registration is the gate.

## Stops being one when

- Their account is deleted. (Soft-delete patterns are not currently
  supported.)

## Examples

- **Alice signs up and verifies her email.** Alice is now a Member.
  She can fill out her profile, browse the directory (if other
  Members have opted in), and bookmark events.
- **Bob is a Boat Owner of "Wind Dancer."** Bob is *also* a Member —
  the Boat Owner role is relational on top of his Membership.

## Distinctions

- **Member is not a `UserRole` row.** It's the absence of an admin or
  manager role, plus the presence of a valid Person row.
- **Member is not the same as a paid membership.** Some product flows
  call `PersonProduct` rows "memberships" (e.g. "Family Membership
  2026"). Those are *entitlements*, not the system role. A Member
  without any active `PersonProduct` is still a Member; they just
  lack certain entitlements like `grants_boat_management`.

## Technical anchor

- **Predicate**: `Person row exists AND has a valid AuthToken or AgentToken`
- **Defined in**: `concorda-api/models/person.py` (the Person model)
- **Enforced by**: `auth_middleware.py::get_current_user_id` — every
  authenticated endpoint requires this gate.
- **Related rules**: see `_index/by_domain.json`.
