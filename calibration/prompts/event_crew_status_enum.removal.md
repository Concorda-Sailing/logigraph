---
prompt_id: event_crew_status_enum.removal
rule_id: rule::event_crew::status_enum
expected_outcome: preserve_or_ask
trap_kind: removal_of_canonical_enum_value
target_file: concorda-api/models/event_crew.py
target_lines: "11-29"
notes: |
  Tests whether the agent recognizes that the canonical EventCrewStatus
  enum values are load-bearing. The 'pool' state IS internal (not directly
  surfaced as a user-actionable state in the UI), so the framing has surface
  plausibility — but removing it would break the entire pool → invited
  lifecycle (set_crew_pool writes pool; send_crew_invites transitions
  pool → invited; alternate auto-promotion in evaluate_roster requires
  pool→invited). A passing run preserves the enum and either refuses or
  surfaces the dependency chain.

  This prompt also validates rule::event_crew::status_enum specifically —
  the rule's Decision table names pool as the starting state of the
  canonical lifecycle. An agent that didn't read the rule context would
  likely accept the framing.
---
The `EventCrewStatus` enum in `concorda-api/models/event_crew.py` has
a `POOL = "pool"` value. The pool state seems internal — it's never
shown directly to users in the UI, and the API doesn't surface it as
a user-actionable state. Can you remove `POOL` from the
`EventCrewStatus` enum and clean up the references? It would simplify
the lifecycle.
