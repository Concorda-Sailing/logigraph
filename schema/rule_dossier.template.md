---
node_id: <rule::category::name>
node_kind: rule
definition_status: stub
last_reviewed: <YYYY-MM-DD>
last_reviewed_against_hash: <node structural_hash>
fan_out: <integer, set by reconcile>
---

<!--
TEMPLATE — Rule dossier.

Quality bar: written for the LLM collaborator first. The Decision table
is the LLM's primary reading surface; treat it as the most important
section and make it exhaustive over realistic boundary conditions.

Required sections (validated by `bin/logigraph validate`):
  - ## The rule
  - ## Why it exists
  - ## Examples
  - ## Counter-examples
  - ## Decision table       (truth-table over conditions)
  - ## Edge cases
  - ## Surfaces

The Decision table is mandatory because it's how the LLM reasons about
boundary conditions reliably. Narrative examples + counter-examples
support prose clarity but don't substitute for an enumerated table.
-->

# <Short rule title>

## The rule

<Single paragraph restating the rule. Same content as the `statement`
field on the node JSON, but with room to clarify.>

## Why it exists

<Rationale. What incident, decision, or design constraint motivated the
rule? Why this rule and not a simpler/different one? This is the section
that lets the LLM judge whether a proposed change preserves intent.>

## Examples

- <Concrete positive case 1: scenario → outcome.>
- <Concrete positive case 2.>
- <Concrete positive case 3 covering a different angle.>

## Counter-examples (what the rule does NOT do)

- <Misconception 1: the rule does **not** ___.>
- <Misconception 2: the rule does **not** apply when ___.>

## Decision table

<Required. Enumerate the realistic boundary conditions and the rule's
verdict on each. The LLM consumer reasons more reliably from a table
than from prose. Use Markdown tables.>

| <Condition 1> | <Condition 2> | <...> | Outcome |
|---------------|---------------|-------|---------|
| <value>       | <value>       | <...> | <verdict> |
| <value>       | <value>       | <...> | <verdict> |

<Optional notes after the table: clarify what fields are gated, what
the hide/show mechanism is, any known inconsistencies between
surfaces.>

## Edge cases

- <Subtlety not captured in the table.>
- <Race condition or ordering question.>
- <Interaction with another rule.>

## Surfaces

<Brief narrative summary of where the rule lives in code. The structured
form is `claims_code` on the node JSON, with current line ranges. This
section explains the *shape* of the implementation: which surfaces
enforce, which display, which emit, which only check.>

- Backend: <description>
- Frontend: <description>
- Mobile / other: <description, if any>

## Open questions

- <Unresolved design or implementation question, if any.>
