#!/usr/bin/env python3
"""
pre_edit_inject.py — Claude Code PreToolUse hook for Edit / Write / MultiEdit.

Reads the tool input from stdin (JSON), resolves the touched file's
(repo, path) tuple, looks up rules that claim depgraph nodes in that
file, and emits a JSON envelope with `additionalContext` containing:

  • For each applicable rule:
      - The rule's title and one-sentence statement.
      - The rule's full dossier (truncated to 200 lines).
      - The role this file plays in the rule (enforces / displays / etc.)
        and the sibling surfaces (other claims with their where: ranges).
      - Plain-language summaries of every domain concept the rule
        references.
      - Stale-claim warning if the depgraph hash has drifted.

  • A trailing reminder that this is intent context, not a license to
    skip thinking.

Latency target: <200ms. Loads the index files lazily (small) and only
the relevant rule + dossier files (one or two per touched file).

Failure modes:
  • If logigraph is uninitialized or the index is missing, surface a
    visible warning rather than silent no-op.
  • If a rule's dossier is missing, inject what we have from the JSON
    and flag the gap.
  • Any unhandled exception → emit a warning and exit 0 (never block
    the edit).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

LOGIGRAPH = Path(
    os.environ.get("LOGIGRAPH_DATA_DIR")
    or os.environ.get("CONCORDA_LOGIGRAPH_PATH")
    or (Path.home() / "concorda" / "logigraph")
).resolve()
DEPGRAPH = Path(
    os.environ.get("DEPGRAPH_DATA_DIR")
    or os.environ.get("CONCORDA_DEPGRAPH_PATH")
    or (Path.home() / "concorda" / "depgraph")
).resolve()
NODES = LOGIGRAPH / "nodes"
RULES_DIR = NODES / "rules"
DOMAIN_DIR = NODES / "domain"
BY_FILE_INDEX = NODES / "_index" / "by_file.json"
CORPUS_META = NODES / "_meta.json"
TELEMETRY_DIR = LOGIGRAPH / "telemetry"
INJECTIONS_LOG = TELEMETRY_DIR / "injections.jsonl"
DOSSIER_LINE_LIMIT = 200
NODE_SCHEMA_VERSION = 2


def emit(envelope: dict) -> None:
    json.dump(envelope, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_warning(message: str) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": f"⚠ logigraph hook: {message}",
            }
        }
    )


def _log_injection(tool: str, file_path: str, rule_ids: list[str]) -> None:
    """Append one JSONL line per rule injected. Used by Phase C telemetry to
    measure injection effectiveness. Failure (disk full, permission denied,
    whatever) is silently swallowed — telemetry must NEVER block the hook.

    One line per rule (not per call) so per-rule aggregation is a simple
    `wc -l` / grep operation."""
    try:
        import datetime as _dt
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
        with INJECTIONS_LOG.open("a") as f:
            for rid in rule_ids:
                f.write(json.dumps({
                    "ts": ts,
                    "kind": "injection",
                    "tool": tool,
                    "file_path": file_path,
                    "rule_id": rid,
                }) + "\n")
    except Exception:
        # Telemetry failure must not propagate. Silent swallow is the policy.
        pass


def target_files(tool_name: str, tool_input: dict) -> list[str]:
    """Return absolute paths of files the tool is about to touch."""
    out: list[str] = []
    if tool_name in ("Edit", "Write", "MultiEdit"):
        p = tool_input.get("file_path")
        if p:
            out.append(p)
    return list(dict.fromkeys(out))


def repo_relative(abs_path: str) -> tuple[str, str] | None:
    """Decompose home-rooted absolute path into (repo, rel)."""
    home = str(Path.home())
    p = Path(abs_path).expanduser().resolve()
    parts = p.parts
    home_parts = Path(home).parts
    if len(parts) <= len(home_parts):
        return None
    if parts[: len(home_parts)] != home_parts:
        return None
    seg = parts[len(home_parts)]
    if not seg.startswith("concorda"):
        return None
    rel = "/".join(parts[len(home_parts) + 1 :])
    return seg, rel


def load_meta_and_status() -> tuple[dict, list[str]]:
    """Read _meta.json. Surface a banner if regen_status != complete."""
    banners: list[str] = []
    meta: dict = {}
    if CORPUS_META.exists():
        try:
            meta = json.loads(CORPUS_META.read_text())
        except (OSError, json.JSONDecodeError):
            banners.append("> ⚠ Logigraph corpus metadata unreadable — run `bin/logigraph regen`.")
            return meta, banners
        status = meta.get("regen_status")
        if status != "complete":
            banners.append(
                f"> ⚠ Logigraph regen `{status or 'unknown'}` — the rule graph may be in a torn state. "
                "Re-run `bin/logigraph regen` before trusting injection."
            )
    else:
        banners.append("> ⚠ Logigraph not initialized (`nodes/_meta.json` missing). Run `bin/logigraph regen`.")
    return meta, banners


def load_index() -> dict[str, list[str]] | None:
    if not BY_FILE_INDEX.exists():
        return None
    try:
        idx = json.loads(BY_FILE_INDEX.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if idx.get("schema_version") != 1:
        return None
    return idx.get("by_file") or {}


def find_rule_node(rule_id: str) -> dict | None:
    for path in RULES_DIR.rglob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("id") == rule_id:
            ver = data.get("schema_version")
            if ver != NODE_SCHEMA_VERSION:
                return None
            return data
    return None


def find_domain_node(node_id: str) -> dict | None:
    for path in DOMAIN_DIR.rglob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("id") == node_id:
            ver = data.get("schema_version")
            if ver != NODE_SCHEMA_VERSION:
                return None
            return data
    return None


def load_dossier(node: dict) -> tuple[str, str]:
    """Return (banner, dossier_text). Truncated to DOSSIER_LINE_LIMIT lines."""
    rel = node.get("dossier")
    if not rel:
        return ("", "_No dossier registered for this node._")
    path = LOGIGRAPH / rel
    if not path.exists():
        return ("", "_Dossier file missing on disk — node JSON exists but text not yet authored._")

    text = path.read_text()
    pinned_hash = None
    status_in_dossier = "current"
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("last_reviewed_against_hash:"):
            pinned_hash = s.split(":", 1)[1].strip().strip('"').strip("'")
        if s.startswith("definition_status:"):
            status_in_dossier = s.split(":", 1)[1].strip()
        if s == "---" and pinned_hash is not None:
            break

    banner = ""
    if pinned_hash and pinned_hash != node.get("structural_hash"):
        banner = (
            f"⚠ STALE DOSSIER — last reviewed against hash {pinned_hash[:12]}, "
            f"current is {(node.get('structural_hash') or '')[:12]}. Treat as advisory."
        )
    elif status_in_dossier == "stub" or node.get("definition_status") == "stub":
        banner = "⚠ STUB DOSSIER — placeholder content only."
    elif status_in_dossier == "llm_drafted" or node.get("definition_status") == "llm_drafted":
        banner = "ℹ LLM-DRAFTED — not yet reviewed by a human."

    lines = text.splitlines()
    total = len(lines)
    if total > DOSSIER_LINE_LIMIT:
        lines = lines[:DOSSIER_LINE_LIMIT] + [
            f"... ({total - DOSSIER_LINE_LIMIT} more lines truncated; see {rel} for full text)"
        ]
    return banner, "\n".join(lines)


def format_sibling_claims(rule: dict, this_file_repo: str, this_file_rel: str) -> str:
    """Render the rule's claims_code as a table, marking the row that
    corresponds to *this* file (the one being edited) so the LLM knows
    where it sits within the rule's scatter."""
    claims = rule.get("claims_code", [])
    if not claims:
        return "_No claims._"

    # Resolve each claim's depgraph_id back to its source file via the
    # depgraph corpus so we can mark the "this is the surface you're
    # editing" row.
    rows = []
    for claim in claims:
        cid = claim.get("depgraph_id", "?")
        role = claim.get("role", "?")
        where = claim.get("where") or "—"
        stale = " ⚠ STALE" if claim.get("stale") else ""
        is_this = _claim_resolves_to(cid, this_file_repo, this_file_rel)
        marker = "← **you are here**" if is_this else ""
        rows.append((cid, role, where, stale, marker))

    out = ["| Surface | Role | Where | |",
           "|---|---|---|---|"]
    for cid, role, where, stale, marker in rows:
        out.append(f"| `{cid}`{stale} | `{role}` | {where} | {marker} |")
    return "\n".join(out)


def _claim_resolves_to(cid: str, this_repo: str, this_rel: str) -> bool:
    """Look up the depgraph node for this claim id and check if its source
    matches the file being edited."""
    dnodes = DEPGRAPH / "nodes"
    if not dnodes.exists():
        return False
    for path in dnodes.rglob("*.json"):
        if path.name.startswith("_") or any(p.startswith("_") for p in path.parts):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("id") == cid:
            src = data.get("source") or {}
            return src.get("repo") == this_repo and src.get("path") == this_rel
    return False


def extract_section(text: str, name: str) -> str:
    """Extract the body of a markdown `## <name>` section. The header line may
    have trailing extra text (e.g. parenthetical clarifier); only the first
    word(s) of the header have to match. Returns the body between this header
    and the next `## ` header (or end of document), stripped."""
    pattern = re.compile(
        rf"^##\s+{re.escape(name)}\b[^\n]*\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _file_match_needles(file_rel: str) -> list[str]:
    """Path tails that, if found in dossier prose, indicate the prose is
    talking about *this* file. Used to filter counter-examples to ones that
    name the surface being edited. Returns several increasingly-specific
    needles — earlier ones are stronger evidence."""
    parts = [p for p in file_rel.split("/") if p]
    needles: list[str] = []
    if len(parts) >= 3:
        needles.append("/".join(parts[-3:]))
    if len(parts) >= 2:
        needles.append("/".join(parts[-2:]))
    if parts:
        needles.append(parts[-1])
    return needles


def filter_counter_examples_for_file(dossier_text: str, file_rel: str) -> list[str]:
    """Return the bullets from the `## Counter-examples` section that mention
    the file being edited. Returns a list of bullet strings (each starting
    with `- `), or empty list if none match (or section absent)."""
    section = extract_section(dossier_text, "Counter-examples")
    if not section:
        return []
    needles = _file_match_needles(file_rel)

    # Split into bullets. A bullet starts with `- ` at the beginning of a line
    # and continues until the next `- ` at line start or end of section.
    chunks = re.split(r"\n(?=- )", section.strip())
    matched: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk.startswith("- "):
            continue
        if any(n in chunk for n in needles):
            matched.append(chunk)
    return matched


PRE_ACTION_CHECKLIST = """### ✋ Before you act

Before issuing the next tool call (Edit/Write/MultiEdit), state in your reasoning:

  1. **Which row of the decision table above covers this edit?** Name the row.
  2. **Does the edit you are about to make produce that row's stated outcome?**
     If yes, proceed.
  3. **If no, why proceed anyway?** State the reason explicitly, or refuse and
     ask the user.

This checklist exists because injected rule context is easy to skim past once
you have committed to a plan. Stating the row out loud forces processing
rather than recognition."""


def render_for_rule(
    rule: dict,
    this_repo: str,
    this_rel: str,
) -> str:
    """Render the rule for PreToolUse injection.

    Section order is calibrated to defeat skimming + goal-anchoring: the most
    decisive content (surfaces, decision table, file-specific
    counter-examples, action checklist) lands first, before the LLM has built
    momentum from reading prose. Title / statement / full dossier / domain
    follow as deeper reference. See plans/quirky-wishing-starfish.md Phase A.
    """
    title = rule.get("title", rule["id"])
    fan_out = rule.get("fan_out") or len(rule.get("claims_code", []))
    statement = rule.get("statement", "")
    banner, dossier = load_dossier(rule)

    parts: list[str] = []

    # 1. Bold attention header — first thing the LLM sees per rule.
    parts.append(f"## 🛑 RULE APPLIES — `{rule['id']}`")
    parts.append(
        f"**Read the decision table and counter-examples below before "
        f"editing this file.** (fan-out: {fan_out}, status: "
        f"{rule.get('definition_status','?')})"
    )
    parts.append("")

    if banner:
        parts.append(f"> {banner}")
        parts.append("")

    # 2. Surfaces table — shows where this file sits in the rule's scatter,
    #    with `← you are here` marker.
    parts.append("### Surfaces of this rule")
    parts.append(format_sibling_claims(rule, this_repo, this_rel))
    parts.append("")

    # 3. Decision table — extracted from the dossier so it is not buried
    #    under several KB of prose. The table is the LLM's primary reading
    #    surface for boundary reasoning.
    decision_table = extract_section(dossier, "Decision table")
    if decision_table:
        parts.append("### Decision table (from dossier)")
        parts.append(decision_table)
        parts.append("")

    # 4. Counter-examples that name *this file* — pulled out so the
    #    file-specific contradictions land before the LLM commits to a plan.
    counter_bullets = filter_counter_examples_for_file(dossier, this_rel)
    if counter_bullets:
        parts.append("### Counter-examples naming this file")
        parts.extend(counter_bullets)
        parts.append("")

    # 5. Pre-action checklist — structured deliberation gate.
    parts.append(PRE_ACTION_CHECKLIST)
    parts.append("")

    # 6. Title / statement (familiar context, less decisive than what
    #    precedes it).
    parts.append(f"### Rule: {title}")
    parts.append(f"**Statement.** {statement}")
    parts.append("")

    # 7. Domain referenced.
    refs = rule.get("references_domain", [])
    if refs:
        parts.append("### Domain referenced")
        for ref in refs:
            ont = find_domain_node(ref)
            if ont:
                parts.append(f"- `{ref}` — {ont.get('summary','')}")
            else:
                parts.append(f"- `{ref}` — _domain node missing (orphan reference)_")
        parts.append("")

    # 8. Full dossier as deep reference.
    parts.append("### Full dossier")
    parts.append(dossier)
    return "\n".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        emit_warning("could not parse hook input")
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    targets = target_files(tool_name, tool_input)
    if not targets:
        return 0

    index = load_index()
    if index is None:
        # Don't warn on every edit when logigraph is uninitialized — many
        # files are not covered, especially during early Phase 0 build-out.
        # The user knows logigraph state from explicit commands.
        return 0

    _, status_banners = load_meta_and_status()

    blocks: list[str] = []
    blocks.extend(status_banners)
    injected_rule_ids: list[str] = []
    primary_target: str | None = None

    for abs_path in targets:
        rr = repo_relative(abs_path)
        if not rr:
            continue
        repo, rel = rr
        key = f"{repo}/{rel}"
        rule_ids = index.get(key) or []
        if not rule_ids:
            continue
        if primary_target is None:
            primary_target = abs_path
        for rid in rule_ids:
            rule = find_rule_node(rid)
            if rule is None:
                blocks.append(
                    f"> ⚠ Rule `{rid}` claimed by index but missing on disk or wrong schema_version. "
                    f"Run `bin/logigraph regen`."
                )
                continue
            blocks.append(render_for_rule(rule, repo, rel))
            injected_rule_ids.append(rid)

    if not blocks:
        return 0

    body = (
        "# 🧭 Concorda logigraph context\n\n"
        + "_Rules and domain that apply to the file you're about to edit. "
        "These describe **intent** — what the system means and why — that "
        "tests/types/lint cannot tell you._\n\n"
        + "\n\n---\n\n".join(blocks)
        + "\n\n---\n\n"
        "_Reminder: rule prose is the canonical statement of intent. If your edit "
        "would violate a decision-table outcome or remove a defensive surface, "
        "pause and confirm._"
    )

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": body,
            }
        }
    )

    if injected_rule_ids and primary_target:
        _log_injection(tool_name, primary_target, injected_rule_ids)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        emit_warning(f"pre_edit_inject crashed: {type(e).__name__}: {e}")
        sys.exit(0)
