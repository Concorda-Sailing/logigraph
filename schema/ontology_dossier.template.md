---
node_id: <role::category::name>
node_kind: ontology
subkind: role
definition_status: stub
last_reviewed: <YYYY-MM-DD>
last_reviewed_against_hash: <node structural_hash>
---

<!--
TEMPLATE — Ontology dossier (role subkind).

Quality bar: written for the LLM collaborator first. Use enumerated lists,
concrete predicates, and short sentences. A non-engineer being able to
read this is a useful proxy for prose clarity, not the calibration
target.

Required sections (validated by `bin/logigraph validate`):
  - ## Plain definition
  - ## They can
  - ## They cannot
  - ## Becomes one when
  - ## Stops being one when
  - ## Examples
  - ## Technical anchor

Resource / action / attribute subkinds use different templates (TBD in
Phase 1). For now, this template covers role::system::* and
role::relational::* nodes.
-->

# <Role Title>

## Plain definition

<One-paragraph plain-English description. Who is this role? What is the
shape of the relationship? E.g. "A Boat Owner is the person whose boat
it is. They registered the boat or were promoted to co-owner. Multiple
owners are allowed; they have equal authority.">

## They can

- <Capability 1, in plain terms.>
- <Capability 2.>
- <Capability 3.>

## They cannot

- <Limit 1.>
- <Limit 2.>

## Becomes one when

- <Predicate that flips this on, in plain terms.>
- <Alternate path if any.>

## Stops being one when

- <Predicate that flips this off.>
- <Edge case (e.g. "the boat is deleted").>

## Examples

- <Concrete sailor-named example. Use seed personas (Alice, Bob, Carol)
  where helpful.>
- <Second example covering a different path to the role.>

## Distinctions

<Optional. How is this concept different from adjacent concepts the LLM
might confuse it with? E.g. "Co-owner is not the same as a Crew Member
with admin permissions — Co-owner has equal authority via the
unanimous-approval promotion process; Crew Member is non-authoritative
regardless of permission bits.">

## Technical anchor

- **Predicate**: `<SQL-ish or set-builder predicate>`
- **Defined in**: `<repo/file.py>` (system roles only)
- **Enforced by**: `<canonical helper / chokepoint>`
- **Related rules**: see `_index/by_ontology.json` for rules that
  reference this node.
