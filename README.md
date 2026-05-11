# Logigraph

A continuously-maintained graph of **business rules** and the
**role/resource/action domain** they reference, with each rule
*claiming* the depgraph code nodes that enforce it.

Sibling to [depgraph](../depgraph/), which tracks structure (what calls
what). Logigraph tracks **intent** (what the system means and which rules
it enforces).

## Why

Concorda already has tools that catch regression and structural drift
(tests, types, lint, architecture tests, code review). What those tools
*cannot* do is hand a fresh-session LLM the **intent** behind the code:
which duplications are intentional, which naming choices grandfather
legacy decisions, which behaviors are load-bearing even without test
coverage, which rules apply that a code reader can't infer from patterns
alone.

The class of bug logigraph targets: **plausibly-correct change that
silently violates intent**. Invisible to tests because the violation
satisfies them. Invisible to review because the reviewer infers from the
same code patterns Claude did.

The primary consumer is the LLM collaborator. Plain-language
definitions are how intent gets encoded; the LLM reads them at edit
time via the PreToolUse hook.

## Layers

```
┌────────────────────────────────────────────────────────────────────┐
│ Logigraph (rules)                                                  │
│  rule statements → reference domain + claim depgraph code        │
├────────────────────────────────────────────────────────────────────┤
│ Domain (roles, resources, actions, attributes)                   │
│  small, slow-changing nouns/verbs                                  │
│  partially extracted (system roles, DB resources)                  │
│  partially authored (relational roles, abstract concepts)          │
├────────────────────────────────────────────────────────────────────┤
│ Depgraph (code)                                                    │
│  AST-derived, deterministic, bit-stable                            │
└────────────────────────────────────────────────────────────────────┘
```

## Layout

```
logigraph/
├── README.md            this file
├── PROCESS.md           authoring flow, conventions, quality bar
├── DRIFT.md             known failure modes
├── bin/logigraph        Python CLI: validate, regen, context
├── nodes/
│   ├── domain/        role/resource/action/attribute node JSON
│   ├── rules/           rule node JSON
│   ├── _index/
│   │   ├── by_code.json        depgraph_id → [rule_ids]
│   │   ├── by_file.json        (repo, path) → [rule_ids]
│   │   └── by_domain.json    domain_id → [rule_ids]
│   ├── _manifests/      per-source extractor manifests
│   ├── _meta.json       regen_status + corpus provenance
│   └── _archive/        tombstoned nodes
├── dossiers/
│   ├── domain/        plain-language definitions of concepts
│   └── rules/           plain-language statements of rules
├── extractors/
│   ├── extract_system_roles.py     reads concorda-api/scripts/seed_roles.py
│   ├── extract_db_resources.py     walks SQLAlchemy models
│   └── reconcile.py                builds indexes, validates claims
├── schema/
│   ├── domain.schema.json
│   ├── rule.schema.json
│   ├── domain_dossier.template.md
│   └── rule_dossier.template.md
└── hooks/
    ├── pre_edit_inject.py      PreToolUse: inject rules + domain
    └── post_edit_regen.py      Stop: refresh indexes on touched files
```

## Schema versioning

Logigraph nodes use `schema_version: 2`. Depgraph uses `schema_version: 1`.
The split lets each system's tools refuse to read the other's nodes if
files are accidentally crossed.

## Status

Phase 0 (tracer bullet) — building.

## See also

- `PROCESS.md` — how to add a rule, how to add an domain node, when
  dossiers need re-review.
- `DRIFT.md` — known failure modes and how the system surfaces them.
- `../depgraph/` — the structural graph this layers on top of.

## License

[MIT](./LICENSE). Copyright (c) 2026 Logan Greenlee.

The software is provided **AS IS**, without warranty of any kind,
express or implied, including but not limited to merchantability,
fitness for a particular purpose, and non-infringement. See the
LICENSE file for the full text.
