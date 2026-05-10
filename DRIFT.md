# Logigraph DRIFT

Known failure modes and how the system surfaces them. Mirror of
depgraph's DRIFT.md, narrowed to the rule + ontology layer.

## 1. Stale claim (depgraph node hash drifted)

**Scenario.** A rule's `claims_code[].depgraph_id` still exists, but the
claimed node's `structural_hash` in the depgraph has changed. The rule's
prose may now be inaccurate about that surface.

**Detection.** `reconcile.py` re-pulls each claim's `remote_hash` from
the current depgraph. Any divergence flips the claim to `stale: true`.

**Surface.** PreToolUse hook on a co-claimed file shows
`⚠ Stale claim: rule R claims this node but the code has changed since
last review.`

**Mitigation.** Re-read the rule against the new code. If the rule
still applies, refresh the claim (`bin/logigraph claim-refresh <rule>
<depgraph_id>`). If the rule no longer applies, drop the claim or
update `claims_code[].role`.

## 2. Orphan rule (claim id no longer exists in depgraph)

**Scenario.** A claimed depgraph node was deleted or renamed; the rule
still references the old id.

**Detection.** `reconcile.py` validates every `claims_code[].depgraph_id`
against the depgraph node corpus. Missing ids fail loud.

**Surface.** `bin/logigraph regen` exits non-zero with a list of
unresolved claims. `bin/logigraph gaps` reports them.

**Mitigation.** Update the rule's claims to point at the renamed/new
node, or remove the claim if the enforcement was deleted.

## 3. Orphan ontology reference

**Scenario.** A rule's `references_ontology` entry points to an
ontology node id that doesn't exist (typo, rename, deleted concept).

**Detection.** `reconcile.py` cross-checks against `nodes/ontology/`.

**Surface.** `bin/logigraph regen` exits non-zero. `bin/logigraph gaps`
reports.

**Mitigation.** Fix the typo, add the missing ontology node, or remove
the reference.

## 4. Stub dossier merged accidentally

**Scenario.** A node JSON exists with `definition_status: stub` but the
dossier wasn't authored. The hook would inject a TODO placeholder as
intent, which is worse than nothing.

**Detection.** `bin/logigraph validate` fails any node with
`definition_status: stub` whose dossier still contains the TODO marker.

**Surface.** Validation error in CI / pre-commit. Hook injection skips
stub nodes (with a banner) rather than emit TODOs.

**Mitigation.** Author the dossier and bump `definition_status`.

## 5. Curation lag (rules out of date with code reality)

**Scenario.** Code changed and now does something the dossier doesn't
describe. No claim is stale (the hash didn't change because the change
was elsewhere); no orphan exists. The dossier is just *wrong*.

**Detection.** Hardest failure mode. Not detectable automatically —
discovered when the LLM acts on the dossier and produces a wrong
result.

**Surface.** None automatic. The fresh-session test in Phase 0
verification is the canary.

**Mitigation.** Treat dossier drift as a bug class with the same
weight as code bugs. When a rule's prose is found to be wrong, update
the dossier and add an entry to a session log; periodically audit.

## 6. Cross-graph schema mismatch

**Scenario.** Logigraph node has `schema_version: 2`. Depgraph tools
read it accidentally and mis-interpret fields. Or vice-versa: a logigraph
hook reads a depgraph node (`schema_version: 1`) and tries to use rule
fields that don't exist.

**Detection.** Schema-version gate in each hook rejects mismatched
nodes loudly.

**Surface.** PreToolUse banner: `⚠ N node(s) skipped due to
schema_version mismatch`.

**Mitigation.** Don't write logigraph node JSON into depgraph
directories or vice-versa. The two corpora live under separate roots.

## 7. Torn regen

**Scenario.** `bin/logigraph regen` was interrupted mid-run.
`_meta.json` reads `regen_status: in_progress`. Indexes are
inconsistent.

**Detection.** PreToolUse hook reads `_meta.json` first.

**Surface.** Banner: `⚠ Regen in_progress — the logigraph may be in a
torn state. Re-run bin/logigraph regen before trusting context.`

**Mitigation.** Re-run regen.

## 8. Ontology drift (concept renamed)

**Scenario.** "Co-owner" gets renamed to "Joint Owner" in the codebase.
Existing rules reference `role::relational::co_owner`, which still
exists as a logigraph node, but is conceptually misaligned.

**Detection.** None automatic. Same shape as #5.

**Mitigation.** Treat ontology renames as structural events: rename
the node id, update every rule's `references_ontology`, regen.
`bin/logigraph rename-ontology <old> <new>` may eventually exist.

## 9. Phantom ontology (referenced but never created)

**Scenario.** A rule mentions `role::relational::watch_captain`, an
ontology node that doesn't yet exist (someone wrote the rule before the
ontology entry).

**Detection.** Same as #3 — orphan ontology reference.

**Surface.** Validation error.

**Mitigation.** Create the ontology node before writing rules that
reference it. Or accept the validation error as a TODO list of
ontology nodes to author.

## See also

- `../depgraph/DRIFT.md` — sibling failure modes for the structural
  graph.
- `PROCESS.md` — authoring flow that prevents most of the above.
