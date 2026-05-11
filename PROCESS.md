# Logigraph PROCESS

How to add, edit, and review nodes. The quality bar is **unambiguous LLM
consumption**: a fresh-session Claude reading a dossier should be able to
answer "what is this?" / "is behavior X consistent with this?" without
ambiguity. A non-engineer being able to read it is a useful proxy for
prose clarity, not the use case.

## Authoring flow

Three stages, tracked by `definition_status` on each node:

1. **stub** — extractor-generated placeholder. Technical anchor is
   filled in (predicate, source path); dossier body is a TODO marker.
2. **llm_drafted** — Claude has filled in the dossier from MEMORY.md,
   flow docs, and code context. Not yet reviewed.
3. **human_reviewed** — Logan signed off after reading. Ready to be
   trusted at edit time.

Stub → drafted → reviewed. Don't skip stages. `bin/logigraph
dossiers --status` reports the count at each stage.

## Adding a rule

1. Pick a stable `id` of the form `rule::<category>::<short_name>`,
   e.g. `rule::crew_visibility::peer_pii_resume_gated`.
2. Write the node JSON at `nodes/rules/<id-slug>.json`. Required fields
   per `schema/rule.schema.json`:
   - `statement` — single-sentence English rule.
   - `references_domain` — list of domain node ids the rule mentions.
   - `claims_code` — list of depgraph node ids the rule lives in, each
     with `role` (enforces / checks / serializes / displays / emits) and
     `where` (file:line range).
   - `source` — pointer to the memory file or design doc the rule came
     from.
3. Author the dossier at `dossiers/rules/<id-slug>.md` from
   `schema/rule_dossier.template.md`. Required sections:
   - `## The rule` — restated for clarity.
   - `## Why it exists` — rationale.
   - `## Examples` — narrative positive cases.
   - `## Counter-examples` — what the rule does NOT do.
   - `## Decision table` — **required**. Truth-table over boundary
     conditions; this is the LLM's primary reading surface.
   - `## Edge cases` — subtleties not in the table.
   - `## Surfaces` — where the rule lives in code.
4. Run `bin/logigraph regen` to validate claims and rebuild indexes.
5. Run `bin/logigraph context <claimed-file>` to confirm injection.

## Adding an domain node

Subkind decides the dossier shape:

- **role** — full `## They can / ## They cannot / ## Becomes one when /
  ## Stops being one when` template. Use for system roles
  (`role::system::<name>`) and relational roles
  (`role::relational::<name>`).
- **resource** — `## What it is / ## Lifecycle / ## Key fields /
  ## Relationships` template (TBD in Phase 1).
- **action** — `## What it does / ## Who can perform / ## Preconditions
  / ## Side effects` template (TBD in Phase 1).
- **attribute** — `## What it represents / ## Allowed values /
  ## Default / ## Set by` template (TBD in Phase 1).

For Phase 0, only the role template exists (`schema/domain_dossier.template.md`).

## Editing a live rule or concept

If the rule's *meaning* changes (not just where it's enforced):
- Bump the rule's `structural_hash` (recompute over statement + domain
  refs + claim ids).
- Set `definition_status: llm_drafted` so the node re-enters review.
- Update the dossier; refresh `last_reviewed_against_hash` in
  frontmatter only after re-reading.

If the rule's *enforcement location* changes (refactor):
- Update `claims_code` entries.
- `bin/logigraph regen` re-pulls `remote_hash` from the depgraph; if a
  claim's code has drifted, the claim is marked stale.

## Quality bar checks

`bin/logigraph validate` enforces:
- JSON-Schema compliance (`schema/domain.schema.json`,
  `schema/rule.schema.json`).
- Required dossier sections present (rule dossiers must have
  `## The rule`, `## Why it exists`, `## Decision table`).
- Every `claims_code[].depgraph_id` exists in the depgraph corpus.
- Every `references_domain` entry exists in `nodes/domain/`.

## See also

- `DRIFT.md` — failure modes and how they surface.
- `schema/` — JSON schemas and dossier templates.
- `../depgraph/PROCESS.md` — sibling system's process docs.
