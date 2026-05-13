---
node_id: <process::category::name>
node_kind: process
definition_status: stub
last_reviewed: <YYYY-MM-DD>
last_reviewed_against_hash: <node structural_hash>
fan_out: <integer, set by reconcile>
---

<!--
TEMPLATE — Process dossier.

Quality bar: written for the LLM collaborator first. The Decision table
is the LLM's primary reading surface; treat it as the most important
section and make it exhaustive over realistic boundary conditions.

Required sections (validated by `bin/logigraph validate`):
  - ## The process
  - ## Why it exists
  - ## Examples
  - ## Counter-examples
  - ## Decision table       (truth-table over conditions / step outcomes)
  - ## Edge cases
  - ## Surfaces

A process node describes a multi-step flow whose steps share a single
transactional scope or a single endpoint. The dossier explains *why*
the steps are grouped (what topology would be lost by splitting them)
and documents the observable invariants across the flow.

The Decision table is mandatory because it's how the LLM reasons about
boundary conditions reliably. For processes, the table typically maps
"which step fails / which condition holds" to "which outcome (error code,
side-effect set, broadcast or no-broadcast)".
-->

# <Short process title>

## The process

<Single paragraph restating what this process does. Same content as the
`description` field on the node JSON, but with room to clarify. Describe
the entry point (endpoint, scheduled job, UI action), the terminal states
(success paths and error paths), and which tables or external systems are
mutated.>

## Why it exists

<Rationale. Why are these steps grouped into one process node rather than
authored as N independent rules? What topology — shared endpoint, shared
transaction, ordering dependency, shared broadcast gate — would be lost
by splitting them? This is the section that lets the LLM judge whether a
refactor preserves the grouping intent.>

## Examples

- <Concrete positive case 1: scenario → outcome, naming the happy path.>
- <Concrete positive case 2 covering a different branch (e.g. idempotent path).>
- <Concrete positive case 3 covering an error path.>

## Counter-examples (what the process does NOT do)

- <Misconception 1: the process does **not** ___.>
- <Misconception 2: this step does **not** run when ___.>

## Decision table

<Required. Enumerate the realistic branch conditions and the process's
verdict on each. The LLM consumer reasons more reliably from a table
than from prose. Use Markdown tables. For processes, columns typically
include the triggering condition or failing step and the outcome
(HTTP code, side-effect set, broadcast or no-broadcast).>

| <Condition / Step> | <Condition 2> | <...> | Outcome |
|--------------------|---------------|-------|---------|
| <value>            | <value>       | <...> | <verdict> |
| <value>            | <value>       | <...> | <verdict> |

<Optional notes after the table: clarify which steps are observationally
distinct even if superficially similar, any known inconsistencies between
branches.>

## Edge cases

- <Subtlety not captured in the table.>
- <Race condition or ordering question.>
- <Interaction with another process or rule.>

## Surfaces

<Brief narrative summary of where the process lives in code. The structured
form is `claims_code` on the node JSON, with current line ranges. This
section explains the *shape* of the implementation: which surfaces are the
entry point, which handle each branch, which emit side-effects or broadcasts.>

- Backend: <description>
- Frontend: <description>
- Mobile / other: <description, if any>

## Open questions

- <Unresolved design or implementation question, if any.>
