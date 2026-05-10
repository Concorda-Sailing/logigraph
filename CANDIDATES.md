# Rule candidates

Candidates surfaced by rule-discovery passes. Author via `bin/logigraph rule-stub <id>` to materialize as a stub node, then `rule-draft` → fill body → `rule-finalize` → review → `rule-bump`.

Maintain this file by hand: remove a candidate when the rule has been authored and `rule-bump`'d to `human_reviewed`; add new candidates as they surface.

---

## Tier 1 — high-leverage, fix-shaped (author first)

### rule::auth::tier_c_org_scope_chokepoint
- **statement**: Every cross-org mutating endpoint that touches an org-owned resource (organization, regatta, event, product, discount, series, billing contact) must funnel its decision through `AuthUser.can_administer_orgs(owning_org_ids)` after resolving the resource's owning-org set, not just check role type.
- **why**: Tier-C audit (commit `058aa8c`, 2026-05-05) closed a security finding where any `org_admin`/`delegate` of one club could mutate another club's records. New mutating endpoints have repeatedly been the regression vector.
- **surfaces**:
  - `routers/organizations.py` PUT/DELETE/contacts — `_require_org_admin_scope`
  - `routers/regattas.py` — `_require_manager` + `_require_regatta_org_scope` + `_require_oa_scope`
  - `routers/products.py:20-31` — `_require_event_org_scope`
  - `auth_middleware.AuthUser.can_administer_orgs` — chokepoint
- **confidence**: high

### rule::boat_ownership::via_boatcrew_not_owner_ids
- **statement**: Boat ownership is the set of `BoatCrew` rows with `role='owner'` and `status='active'`; the legacy `Boat.owner_ids` JSON column must not be the source of truth for new code.
- **why**: Multiple model dossiers warn against `owner_ids`. Co-owner promotion flows through the `Approval` system; multiple owners are equal in authority.
- **surfaces**:
  - `routers/boats.py:63` — `_require_owner`
  - `routers/boatfinder.py::_get_boat_owner` — first BoatCrew owner active
  - `routers/profile.py::_owner_query`
  - `routers/invite.py::accept_invite` — coowner accept flips role
- **confidence**: high

### rule::events::personal_event_excluded_from_public_listings
- **statement**: Public event-listing endpoints must filter `Event.category != "personal"`, and personal events must always carry `slug = None` (never `""`) to dodge SQLite UNIQUE-collision; personal events are visible only to their `owner_id`.
- **why**: Commit `4fd165d` fixed slug-UNIQUE collision. The category-filter has bitten on commits `7570175` → revert `57f2e00` → re-fix `b887b73` (date-floor regression). Missing the filter leaks calendar rows.
- **surfaces**:
  - `routers/events.py:111, 134, 730, 845` — four list filter sites
  - `Event.__init__` — `slug=None` for personal
  - `routers/events.py:89` — viewer-scoped to `owner_id`
- **confidence**: high

### rule::payments::transaction_person_binding
- **statement**: Redeeming a paid `transaction_id` must require `Transaction.person_id == current_user.id` OR both NULL (guest-checkout); the NULL-NULL branch must not be tightened without preserving the guest path.
- **why**: Pre-fix, any logged-in user could redeem someone else's payment (`74962cb`). Guest checkout (`3750138`) requires NULL-NULL.
- **surfaces**:
  - `routers/events.py:1694-1727` — register_for_event binding
  - `routers/payments.py` — three create branches
  - `routers/payments.py:474-503` — Stripe webhook lifecycle
  - `routers/events.py:1715-1724` — lazy-promote when user beats webhook
- **confidence**: high

### rule::datetime::utc_aware_storage_and_org_tz_display
- **statement**: All datetime columns use `UtcDateTime` (naive-as-UTC stored, aware on read); UI rendering goes through `formatInOrgTz`/`ymdInOrgTz`; `<input type="datetime-local">` save paths funnel through `orgInputToUtcIso`. No raw `Date.getHours()`, `toLocaleString()` without `timeZone`, or `new Date().toISOString().slice()` shortcuts.
- **why**: Memories `feedback_naive_datetime_convention` and `feedback_timezone_helpers_mandatory`; 2026-05-07 audit found ~30 components drifting; pre-2026-05-06 imports have ~5h drift.
- **surfaces**:
  - `concorda-web/src/lib/datetime.ts::formatInOrgTz` — 70 dependents
  - `ymdInOrgTz` — 35+ dependents
  - `orgInputToUtcIso` — 13 form-save sites
  - `concorda-api/models/event.py::Event` — `UtcDateTime` columns
- **confidence**: high

---

## Tier 2 — strong but less acute

### rule::ws::event_type_string_contract
- **statement**: WebSocket event type names are a stable string contract between `broadcast_event` and `useWsFreshness`; renaming silently breaks every consumer until they redeploy.
- **why**: 41 emit sites, 14+ subscriber sites; no shared registry across repos.
- **surfaces**: `concorda-api/utils/websocket_manager.py` constants; `concorda-web/src/hooks/use-ws-freshness.ts`; `concorda-web/src/hooks/use-boats.ts`.
- **confidence**: high

### rule::auth::privilege_escalation_level_guard
- **statement**: Endpoints that assign/revoke a role or edit a role's permissions must reject when the target role's `Role.level` exceeds the actor's max held level.
- **why**: Two security commits (`33a37a3`, `650233f`) closed this class.
- **surfaces**: `routers/roles.py:108`, `:217`, `:274`; `routers/admin.py::_require_can_modify_user`.
- **confidence**: high

### rule::membership::single_membership_personproduct
- **statement**: A Person holds at most one Membership-category `PersonProduct`; `/membership/upgrade` enforces by deleting all existing Membership rows then inserting in one transaction.
- **why**: Procedural-not-DB-enforced; inserting I/O between delete and commit breaks atomicity. Boat Owner / Co-Owner merged in `7e649cf`.
- **surfaces**: `routers/profile.py:1373-1388`; `services/approvals.py:21-31`; `routers/payments.py:151-170`.
- **confidence**: high

### rule::ticket_inventory::registration_table_is_the_ledger
- **statement**: A Product's sold-out check counts `EventRegistration` rows where `status == "Confirmed"` and `product_id == p.id`; there is no decrement counter on `Product`. Cancelled rows free the seat and free the email for re-registration.
- **why**: Three call sites (display, optimistic, final guard) must replicate exactly. TOCTOU-vulnerable today.
- **surfaces**: `routers/events.py:1473-1481`, `:1530-1545`, `:1684-1696`; dedup at `:1550-1559`, `:1736-1743`.
- **confidence**: high

### rule::boat_finder::published_flag_gates_visibility
- **statement**: Boat-finder visibility is gated on `BoatResume.published == True`. Per-race "looking for crew" is `SailingEvent.accept_crew_requests`, not `BoatResume.accepting_crew`.
- **why**: Commit `6c9b5f3` (2026-05-06) fixed the conflation of static boat bio vs. per-event toggle.
- **surfaces**: `routers/boatfinder.py:87,131,176,229,292`; `routers/crewfinder.py:82,183`; `routers/profile.py:1020`.
- **confidence**: high

### rule::crewfinder::opt_in_is_the_publish_signal
- **statement**: The crewfinder browseable predicate is `Person.preferences["crewfinder"]["opt_in"]` AND not in `disabled_permissions`, NOT "has a `SailingResume` row." `services/visibility.py::has_published_resume` is the canonical predicate.
- **why**: The most common LLM mistake on this surface; gating on `SailingResume IS NOT NULL` over- or under-exposes.
- **surfaces**: `services/visibility.py::has_published_resume`; `routers/crewfinder.py`; `schemas/event_crew.py::EventCrewRead.resume_published`; `routers/events.py::_event_crew_to_read`; `routers/boats.py::list_visible_crew`.
- **confidence**: high

---

## Tier 3 — lower value as formal rules

### rule::regatta::naming_and_qualifier_vocabulary
- **statement**: Regatta `course_type` is one of six lowercase strings; `qualifier` is JSON list of `{Q, P, SH, O, J, S, W, H}` with Q/P mutually exclusive; `scoring_system` is a rating-system list. Pursuit is a qualifier (`P`), not a course type.
- **why**: `docs/regatta/rules.md` baked into prompts; pursuit-conflation regressed once during Apr 8 cleanup.
- **surfaces**: `models/regatta.py::Regatta`; `docs/regatta/rules.md`; `concorda-web` UI icon-key; `scripts/season_bundle/upsert.py`.
- **confidence**: medium
- **note**: Better as docs reference than injection rule.

### rule::roles::system_v_relational_separation
- **statement**: System roles (`UserRole.role.name`) and relational roles (`BoatCrew.role`) live on separate tables, are checked through different code paths, and must not be conflated. Boat-management entitlement gates on a `TemporalProduct.grants_boat_management` flag, not on any `UserRole`.
- **why**: `UserRole` dossier explicitly warns "DO NOT confuse"; the coowner rule sits on the entitlement, not the role.
- **surfaces**: `models/role.py::UserRole`; `models/boat_crew.py::BoatCrew.role`; `services/approvals.py::_has_boat_management`; `auth_middleware.py::AuthUser`.
- **confidence**: medium
- **note**: Architectural framing; less actionable as injection.
