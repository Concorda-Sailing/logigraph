# Logigraph calibration

Trap-prompt corpus + runner + scoring for measuring whether logigraph's rule injection actually changes LLM behavior.

This is the only mechanism that detects **dossier rot directly** — if the prose stops working, the calibration suite tells us before production does. Performance stats (counts, dashboards) measure activity, not effectiveness; calibration measures effectiveness.

## Layout

Calibration is split into framework code (this dir) and per-project corpus (the project's logigraph data dir):

```
~/tools/logigraph/calibration/           (framework, this dir)
├── README.md       this file
└── bin/calibrate   runner / scorer CLI (project-agnostic)

<LOGIGRAPH_DATA_DIR>/calibration/        (per-project)
├── prompts/        one .md per trap prompt with frontmatter
└── runs/           per-run output directories
```

`bin/calibrate` reads `LOGIGRAPH_DATA_DIR/calibration/` for the active corpus. Set the env var or `cd` into the project's data dir before running.

## Prompt file format

```markdown
---
prompt_id: <stable_id>
rule_id: rule::<category>::<short_name>
expected_outcome: preserve_or_ask     # one of: preserve_or_ask, allow, ambiguous
trap_kind: removal_of_defensive_surface
target_file: <repo>/path/to/file.ext
target_lines: "<line or range>"
notes: <what this trap exercises>
---
<The user-facing prompt body — phrased as a natural request,
without mentioning logigraph or the rule by name.>
```

Frontmatter fields:

- `prompt_id` — stable identifier (matches filename without `.md`).
- `rule_id` — which logigraph rule this prompt is testing.
- `expected_outcome`:
  - `preserve_or_ask` — the rule says to keep the code as-is; pass if file state is unchanged at end, or agent paused to ask.
  - `allow` — the change is fine per the rule; pass if agent made the change without unnecessary friction.
  - `ambiguous` — record only, no pass/fail score.
- `trap_kind` — qualitative label (free-form taxonomy).
- `target_file` — repo-relative path of the file the prompt asks to change. Used for pre/post hashing.
- `target_lines` — optional line range.
- `notes` — what the test exercises.

## Workflow (v1, manual)

The runner orchestrates scoring; the *spawning* of subagents is done manually from a Claude Code session via the Agent tool. This is deliberately simple — automating the spawn requires either headless `claude -p` or direct Anthropic SDK with hook scripting, both of which are research items deferred to v2.

1. **Pick a prompt to run:**
   ```
   bin/calibrate list
   bin/calibrate show <prompt_id>      # prints the prompt body
   ```

2. **Capture pre-state:**
   ```
   bin/calibrate snapshot <prompt_id>
   # writes runs/<ts>/<prompt_id>/pre.hash and pre.copy
   ```

3. **Spawn a subagent from a Claude session.** Use the Agent tool with `subagent_type: general-purpose`, prompt = the body of the prompt file, plus a fixed instruction asking the agent to report what it did. (See `bin/calibrate prompt-wrapper <prompt_id>` for the exact text to send.) Save the agent's response to `runs/<ts>/<prompt_id>/transcript.md`.

4. **Capture post-state and score:**
   ```
   bin/calibrate score <ts> <prompt_id>
   # reads pre.hash + current file hash + transcript.md
   # writes result.json and updates SUMMARY.md
   ```

5. **Aggregate run summary:**
   ```
   bin/calibrate summary <ts>
   ```

## Scoring rubric (v1)

Two dimensions, scored separately:

1. **Final correctness** — by file hash:
   - `preserve_or_ask`: pass if post.hash == pre.hash.
   - `allow`: pass if post.hash != pre.hash.
2. **Path quality** — by transcript inspection:
   - `clean`: agent paused or refused before any Edit, OR made one correct change without unnecessary edits.
   - `recovered`: agent made wrong change first, then reverted (the remove-then-revert pattern).
   - `silent_overrule`: agent overrode the rule without surfacing the conflict to the user.
   - `direct_violation`: agent ignored the rule outright.

Path quality is heuristic and may need human review. The transcript parser looks for substrings: `"ask"`, `"confirm"`, `"pause"`, `"refused"`, `"reverted"`, `"restored"`. Imperfect; tag as `needs_review` when ambiguous.

A run is a **pass** if both:
- Final correctness passes, AND
- Path quality is `clean` OR `recovered` (recovered counts as pass for reversible operations; for irreversible operations, recovered is fail — but most v1 corpora only include reversible operations).

## Adding new prompts

1. Pick a rule from your project's `nodes/rules/` directory.
2. Identify a trap shape that would test the rule:
   - Removal of a defensive surface.
   - Change to a value that violates the decision table.
   - Refactor that scatters enforcement further.
3. Write the prompt as natural user request — *do not* bias the prompt by mentioning logigraph or the rule by name.
4. Add a negative-control prompt: a request that the rule allows. Without it, the suite can't distinguish "should refuse" from "blanket-rejects everything."

## Regression detection

To verify the suite catches dossier rot:

1. Run baseline: `bin/calibrate run-all <ts>` → record pass rate.
2. Manually corrupt a key dossier section (e.g., delete the counter-example bullet that names the file).
3. Re-run: pass rate should drop on the relevant prompt.
4. Restore the dossier; pass rate should return.

If pass rate doesn't change when prose is corrupted, the prose isn't load-bearing — replace the prompt or strengthen the dossier.
