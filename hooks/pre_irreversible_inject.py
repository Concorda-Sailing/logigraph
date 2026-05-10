#!/usr/bin/env python3
"""
pre_irreversible_inject.py — PreToolUse hook for irreversible operations.

Independent of logigraph's rule injection. Watches for tool calls in
classes that cannot be undone with `git stash` or `cp backup`, and
injects a structured "before you act" prompt that forces the LLM to
state goal / preconditions / recovery in its reasoning before executing.

Detects two action classes:

  1. Bash commands that mutate filesystem / remote state:
       rm, git push, git reset --hard, git commit --amend, curl -X
       (POST|PUT|DELETE|PATCH), psql, bq query (mutating), and a few
       common destructive shapes.

  2. MCP write tools, by name pattern:
       mcp__*__(create|send|delete|copy|update|label|unlabel|patch|
                move|cart|publish|deploy|run|execute)

The matcher in settings.json filters to `Bash|mcp__.*` to keep this
hook off pure-read MCP calls (list/search/get/read/download).

Failure mode handling:
  - Unparseable input → emit warning, exit 0 (never block).
  - No match on Bash command → silent return (no injection).
  - Any unhandled exception → emit warning, exit 0.
"""

from __future__ import annotations

import json
import re
import sys


# Bash patterns. Each entry: (compiled regex, short label).
# Designed to match on word boundaries so substrings like `term` don't
# trigger on benign content. The label is surfaced in the injection so
# the LLM knows what flagged.
BASH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*[rRfF]|--recursive|--force)"), "rm with -r/-f flags"),
    (re.compile(r"\bgit\s+push\b(?!\s+--dry-run\b)"), "git push (real, not dry-run)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bgit\s+commit\s+--amend\b"), "git commit --amend (rewrites history)"),
    (re.compile(r"\bgit\s+rebase\b(?!\s+--abort\b|\s+--continue\b)"), "git rebase"),
    (re.compile(r"\bgit\s+branch\s+-D\b"), "git branch -D (force-delete)"),
    (re.compile(r"\bgit\s+checkout\s+--\s+\."), "git checkout -- . (discards changes)"),
    (re.compile(r"\bgit\s+restore\s+(?:--worktree\s+)?\."), "git restore . (discards changes)"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*[fF]"), "git clean -f"),
    (re.compile(r"\bcurl\b[^|;&]*-X\s*['\"]?(?:POST|PUT|DELETE|PATCH)\b"), "curl with mutating verb"),
    (re.compile(r"\bcurl\b[^|;&]*--data\b"), "curl with --data (POST-shaped)"),
    (re.compile(r"\bpsql\b[^|;&]*-c\s+['\"](?:DROP|DELETE|TRUNCATE|UPDATE|ALTER)\b", re.IGNORECASE), "psql mutating SQL"),
    (re.compile(r"\bbq\s+(?:query|rm|cp|mk\s+--force)\b"), "bq mutating command"),
    (re.compile(r"\bdrop\s+(?:table|database|schema)\b", re.IGNORECASE), "DROP statement"),
    (re.compile(r"\bgcloud\s+\S+\s+(?:delete|update|patch|create)\b"), "gcloud mutating command"),
    (re.compile(r"\baws\s+\S+\s+(?:delete|put|update|create)-\S+"), "aws mutating command"),
    (re.compile(r"\bsudo\b"), "sudo (privileged execution)"),
    (re.compile(r"\bdd\s+if=.*\s+of="), "dd (raw disk write)"),
    (re.compile(r">\s*/dev/(?:sd|nvme|hd|disk)"), "redirection to block device"),
    (re.compile(r"\bdocker\s+(?:rm|rmi|kill|stop)\s+"), "docker destructive command"),
    (re.compile(r"\bkubectl\s+(?:delete|apply|patch|replace)\b"), "kubectl mutating command"),
    (re.compile(r"\bsystemctl\s+(?:stop|restart|disable|kill)\b"), "systemctl service control"),
    (re.compile(r"\bsystemctl\s+--user\s+(?:stop|restart|disable|kill)\b"), "systemctl --user service control"),
    (re.compile(r"\bnpm\s+publish\b"), "npm publish"),
    (re.compile(r"\bpip\s+(?:install|uninstall)\s+(?!.*--dry-run)"), "pip install/uninstall (real)"),
    (re.compile(r"\b(?:make|just|task)\s+(?:deploy|publish|release|prod)\b"), "deploy / release target"),
]

# MCP write-action name pattern (caller-side filter; matches the tool
# name passed by the harness). The settings.json matcher should be
# `Bash|mcp__.*` and this hook then narrows to writes.
MCP_WRITE_PATTERN = re.compile(
    r"^mcp__[a-zA-Z0-9_]+__("
    r"create|send|delete|copy|update|label|unlabel|patch|move|cart|"
    r"publish|deploy|run|execute|stop|cancel|disable|enable|reset|"
    r"add|remove|set|put|post|write|insert|merge|approve|reject"
    r")(?:_|$)"
)


def emit(envelope: dict) -> None:
    json.dump(envelope, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_warning(message: str) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": f"⚠ irreversibility hook: {message}",
            }
        }
    )


def detect_bash(command: str) -> list[str]:
    """Return list of human-readable labels for irreversibility patterns
    matched in a Bash command. Empty list means no match."""
    matches: list[str] = []
    for pattern, label in BASH_PATTERNS:
        if pattern.search(command):
            matches.append(label)
    return matches


def detect_mcp(tool_name: str) -> bool:
    return bool(MCP_WRITE_PATTERN.match(tool_name))


def render_injection(tool_name: str, reasons: list[str], detail: str) -> str:
    """The structured deliberation prompt. Lead with attention header so it
    isn't skimmed past; close with the structured questions."""
    parts = [
        "## ⚠ IRREVERSIBLE ACTION",
        "",
        f"**Tool:** `{tool_name}`",
    ]
    if reasons:
        parts.append("**Flagged because:** " + "; ".join(reasons))
    if detail:
        parts.append("")
        parts.append(f"```\n{detail}\n```")
    parts.append("")
    parts.append(
        "**Before executing, state in your reasoning:**\n\n"
        "1. **Goal** — what do you want to be true after this runs, in plain English?\n"
        "2. **Preconditions** — what assumptions are you making about the world right now? "
        "How did you verify each?\n"
        "3. **Recovery** — if this is wrong, what does undoing it look like? If recovery is "
        "expensive or impossible, your bar for proceeding should be higher.\n\n"
        "If any of the three are unclear, **ask before executing.** This is the class of "
        "action where a remove-then-revert pattern doesn't save you."
    )
    return "\n".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        emit_warning("could not parse hook input")
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not command:
            return 0
        reasons = detect_bash(command)
        if not reasons:
            return 0
        body = render_injection(tool_name, reasons, command.strip())
    elif detect_mcp(tool_name):
        # For MCP writes, surface the input as detail so the LLM sees the
        # exact payload it's about to send.
        try:
            detail = json.dumps(tool_input, indent=2)
        except (TypeError, ValueError):
            detail = repr(tool_input)
        body = render_injection(tool_name, ["MCP write tool"], detail)
    else:
        return 0

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": body,
            }
        }
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        emit_warning(f"pre_irreversible_inject crashed: {type(e).__name__}: {e}")
        sys.exit(0)
