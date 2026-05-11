# Migration — pre-config to per-repo `project.toml`

If your project's logigraph data dir was wired to the old framework (pre-config-driven, with hardcoded repo names and Concorda-coupled paths), you need the changes below to keep working with the current `~/tools/logigraph/`.

The framework is no longer project-coupled. Everything project-specific is read from `<LOGIGRAPH_DATA_DIR>/project.toml`.

## 1. Rewrite `project.toml` to per-repo tables

**Before** (Concorda-flavored, minimal):

```toml
[project]
name = "concorda"

[depgraph]
data_dir = "~/concorda/depgraph"
```

**After** (adds `[repos.*]` + `primary_repo`, same shape as depgraph's):

```toml
[project]
name = "<project>"
primary_repo = "api"   # whose git HEAD stamps corpus-meta git_commit

# Logigraph claims against this depgraph corpus — required for reconcile
# to validate rule claims against depgraph node ids.
[depgraph]
data_dir = "~/<project>/depgraph"

# Tracked repos. Logigraph has no extractors today (Phase 1 will add
# extract_system_roles / extract_db_resources), but the [repos.*] shape
# matches depgraph's so primary_repo resolution + path matching work
# uniformly across both frameworks.

[repos.api]
path = "~/<project>-api"

[repos.web]
path = "~/<project>-web"
```

`primary_repo` is the key whose `path` is resolved to find `.git/HEAD` — that 12-char short hash stamps `nodes/_meta.json::git_commit` on every regen. If unset, the framework falls back to the first `[repos.*]` table.

## 2. Set `LOGIGRAPH_DATA_DIR` explicitly

The previous default of `~/concorda/logigraph` is gone. Two options:

- **Recommended**: every Claude Code hook in `.claude/settings.json` should already prefix its command with `LOGIGRAPH_DATA_DIR=/path/to/<project>/logigraph`. Verify that's still true.
- **CLI usage**: either export `LOGIGRAPH_DATA_DIR` in your shell rc, or `cd` into a directory containing `project.toml + nodes/` before running `bin/logigraph`. The framework walks cwd-ancestors to find it; otherwise it fails loudly with a helpful message.

The legacy env var `CONCORDA_LOGIGRAPH_PATH` is gone — use `LOGIGRAPH_DATA_DIR`.

## 3. Move project-specific calibration content into the data dir

If you had calibration prompts and runs checked in under `~/tools/logigraph/calibration/{prompts,runs}/`, they now belong in `<LOGIGRAPH_DATA_DIR>/calibration/{prompts,runs}/`. The framework's `calibration/` only ships the project-agnostic runner (`bin/calibrate`) and a generic README.

`bin/calibrate` reads `LOGIGRAPH_DATA_DIR/calibration/` automatically — no flag needed.

## 4. Update legacy schema-id references (if any)

The JSON-Schema `$id` values were renamed for consistency:

- `concorda.logigraph.domain` → `logigraph.domain`
- `concorda.logigraph.rule` → `logigraph.rule`

If anything in your project pinned to the old `$id` string (e.g. for external validation), update the reference. The validation logic in `bin/logigraph validate` matches on the schema file path, not the `$id`, so internal validation is unaffected.

## 5. Smoke-test

```bash
LOGIGRAPH_DATA_DIR=/path/to/<project>/logigraph bin/logigraph regen
LOGIGRAPH_DATA_DIR=/path/to/<project>/logigraph bin/logigraph self-check
LOGIGRAPH_DATA_DIR=/path/to/<project>/logigraph bin/logigraph validate
```

`self-check` synthesizes its fake file path from your first configured `[repos.*]` table.

## What didn't change

- Rule + domain JSON shapes, dossier markdown shapes.
- Index layouts (`by_code.json`, `by_file.json`, `by_domain.json`).
- `references_domain`, `claims_code`, dossier-section enforcement.
- Mediation-collision detection (intentional design-defect signal).
- PreToolUse / Stop hook contract.

Your existing rules, domain nodes, dossiers, and indexes all keep working — this migration is purely about how the framework finds and dispatches over your project's data.
