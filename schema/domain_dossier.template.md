---
node_id: <domain::subkind::name>
node_kind: domain
subkind: <role|resource|relationship|attribute>
definition_status: stub
last_reviewed: <YYYY-MM-DD>
last_reviewed_against_hash: <node structural_hash>
---

<!--
TEMPLATE — Domain dossier.

Quality bar: written for the LLM collaborator first. Use enumerated lists,
concrete predicates, and short sentences. A non-engineer being able to
read this is a useful proxy for prose clarity, not the calibration
target.

Required sections (validated by `bin/logigraph validate`):
  - ## The thing
  - ## Why it exists
  - ## Examples
  - ## Counter-examples
  - ## Decision table
  - ## Edge cases
  - ## Surfaces
  - ## Open questions

The first section heading differs by subkind but the body structure is
the same. For role subkinds, the paragraph under `## The thing` describes
who holds this role and by what predicate. For resource subkinds, it
describes the entity and its identity tuple. For relationship and
attribute subkinds, it describes the pairing or the field.

The Decision table is mandatory: enumerate the realistic boundary
conditions and the domain concept's verdict on each (e.g. "does this
predicate qualify someone as an X?"). Narrative examples + counter-examples
support prose clarity but don't substitute for an enumerated table.
-->

# <Domain concept title>

## The thing

<Single paragraph: what is this concept? For a role: who is this person and
what predicate qualifies them? For a resource: what row/entity does this name?
What is its identity key? For a relationship: what two nodes does it connect,
and under what conditions? For an attribute: what field, what type, and what
does it control?>

## Why it exists

<Rationale. What real-world fact, design constraint, or business decision
motivated separating this into its own node? Why is it a first-class concept
rather than an implementation detail or a property of another node? This is the
section that lets the LLM judge whether a proposed refactor preserves intent.>

## Examples

- <Concrete positive case 1: who/what qualifies, and why.>
- <Concrete positive case 2 covering a different path.>
- <Concrete positive case 3 covering a different angle.>

## Counter-examples (what this is NOT)

- <Adjacent concept 1 that could be confused with this: how it differs.>
- <Misconception 2: this concept does **not** ___.>

## Decision table

<Required. Enumerate the realistic boundary conditions and the verdict
on each (e.g. "does this predicate hold?", "is this resource visible?",
"is this relationship active?"). Use Markdown tables.>

| <Condition 1> | <Condition 2> | <...> | Outcome |
|---------------|---------------|-------|---------|
| <value>       | <value>       | <...> | <verdict> |
| <value>       | <value>       | <...> | <verdict> |

<Optional notes after the table: known inconsistencies, legacy paths,
future-state intent.>

## Edge cases

- <Subtlety not captured in the table.>
- <Interaction with another domain concept or rule.>
- <Lifecycle edge: what happens when a parent resource is deleted?
  What happens during a role transition?>

## Surfaces

<Where does this concept live in code? Which models, helpers, or
chokepoints are the canonical source of truth? The structured form
is `claims_code` on the node JSON, with current line ranges. This
section explains the *shape*: which surfaces enforce, which display,
which emit, which only check.>

- Backend: <description>
- Frontend: <description>
- Mobile / other: <description, if any>

## Open questions

- <Unresolved design or implementation question, if any.>
