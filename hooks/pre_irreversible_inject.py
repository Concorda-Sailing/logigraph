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
import shlex
import sys


# Shell control operators that start a new command segment.
SHELL_OPERATORS = {"&&", "||", ";", "|", "&", "|&"}


def _has_short_flag(args: list[str], letters: str) -> bool:
    """True if any token in `args` is a short flag like `-r`, `-rf`,
    `-fr` containing any of the given `letters`. Doesn't false-positive
    on long flags (`--foo`) or on arguments (`-c "DROP..."`)."""
    for t in args:
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            if any(c in t[1:] for c in letters):
                return True
    return False


def _check_segment(seg: list[str]) -> list[str]:
    """Return labels for irreversibility patterns matching a single
    command segment (list of tokens, no shell operators).

    Tokens come from shlex, so quoted arguments are single tokens —
    `grep "git push"` is `["grep", "-n", "git push", "file"]` and the
    "git push" substring never appears as adjacent tokens."""
    if not seg:
        return []
    matches: list[str] = []
    first = seg[0]
    rest = seg[1:]

    if first == "sudo":
        matches.append("sudo (privileged execution)")
        # Skip optional sudo flags (-u user, -E, etc.) and recurse on the
        # actual command after sudo. `sudo rm -rf /` should match both
        # `sudo` and `rm with -r/-f flags`, not just sudo.
        idx = 1
        while idx < len(seg) and seg[idx].startswith("-"):
            # `-u user`, `-g group` take a value
            if seg[idx] in ("-u", "-g", "--user", "--group") and idx + 1 < len(seg):
                idx += 2
            else:
                idx += 1
        inner = seg[idx:]
        if inner:
            for label in _check_segment(inner):
                if label not in matches:
                    matches.append(label)

    if first == "rm" and _has_short_flag(rest, "rRfF"):
        matches.append("rm with -r/-f flags")
    if first == "rm" and any(t in ("--recursive", "--force") for t in rest):
        matches.append("rm with -r/-f flags")

    if first == "git" and rest:
        sub = rest[0]
        args = rest[1:]
        if sub == "push" and "--dry-run" not in args:
            matches.append("git push (real, not dry-run)")
        elif sub == "reset" and "--hard" in args:
            matches.append("git reset --hard")
        elif sub == "commit" and "--amend" in args:
            matches.append("git commit --amend (rewrites history)")
        elif sub == "rebase" and not any(a in ("--abort", "--continue") for a in args):
            matches.append("git rebase")
        elif sub == "branch" and "-D" in args:
            matches.append("git branch -D (force-delete)")
        elif sub == "checkout" and len(args) >= 2 and args[0] == "--" and args[1] == ".":
            matches.append("git checkout -- . (discards changes)")
        elif sub == "restore":
            if "." in args or ("--worktree" in args and "." in args):
                matches.append("git restore . (discards changes)")
        elif sub == "clean" and _has_short_flag(args, "fF"):
            matches.append("git clean -f")

    if first == "curl":
        # -X POST/PUT/DELETE/PATCH
        for i, t in enumerate(rest):
            verb = None
            if t == "-X" and i + 1 < len(rest):
                verb = rest[i + 1].upper()
            elif t.startswith("-X"):
                verb = t[2:].upper()
            if verb in ("POST", "PUT", "DELETE", "PATCH"):
                matches.append("curl with mutating verb")
                break
        if any(t == "--data" or t.startswith("--data=") or t in ("-d",) for t in rest):
            matches.append("curl with --data (POST-shaped)")

    if first == "psql":
        for i, t in enumerate(rest):
            if t == "-c" and i + 1 < len(rest):
                sql = rest[i + 1].lstrip().upper()
                if any(sql.startswith(v) for v in ("DROP", "DELETE", "TRUNCATE", "UPDATE", "ALTER")):
                    matches.append("psql mutating SQL")
                    break

    if first == "bq" and rest:
        sub = rest[0]
        if sub in ("query", "rm", "cp"):
            matches.append("bq mutating command")
        elif sub == "mk" and "--force" in rest:
            matches.append("bq mutating command")

    if first == "gcloud":
        # Real gcloud commands have variable depth: `gcloud <group> [<subgroup>...] <verb> [args]`.
        # E.g. `gcloud compute instances delete foo`. Scan all positional tokens (skip flags)
        # for the destructive verb rather than pinning it to a fixed index.
        positionals = [t for t in rest if not t.startswith("-")]
        verb = next((t for t in positionals if t in ("delete", "update", "patch", "create")), None)
        if verb:
            matches.append("gcloud mutating command")

    if first == "aws" and len(rest) >= 2:
        action = rest[1]
        if any(action.startswith(p + "-") for p in ("delete", "put", "update", "create")):
            matches.append("aws mutating command")

    if first == "dd":
        if any(t.startswith("if=") for t in rest) and any(t.startswith("of=") for t in rest):
            matches.append("dd (raw disk write)")

    if first == "docker" and rest and rest[0] in ("rm", "rmi", "kill", "stop"):
        matches.append("docker destructive command")

    if first == "kubectl" and rest and rest[0] in ("delete", "apply", "patch", "replace"):
        matches.append("kubectl mutating command")

    if first == "systemctl":
        # Possibly `--user` before the verb.
        idx = 1 if rest and rest[0] == "--user" else 0
        if len(rest) > idx and rest[idx] in ("stop", "restart", "disable", "kill"):
            label = "systemctl --user service control" if idx == 1 else "systemctl service control"
            matches.append(label)

    if first == "npm" and rest and rest[0] == "publish":
        matches.append("npm publish")

    if first == "pip" and rest and rest[0] in ("install", "uninstall"):
        if "--dry-run" not in rest:
            matches.append("pip install/uninstall (real)")

    if first in ("make", "just", "task") and rest and rest[0] in ("deploy", "publish", "release", "prod"):
        matches.append("deploy / release target")

    # `> /dev/sda` block-device redirection — shlex emits `>` as a token.
    for i, t in enumerate(seg):
        if t == ">" and i + 1 < len(seg):
            if re.match(r"^/dev/(?:sd|nvme|hd|disk)", seg[i + 1]):
                matches.append("redirection to block device")
                break

    return matches

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
    """Return human-readable labels for irreversibility patterns matched
    in a Bash command. Empty list means no match.

    Strategy: shlex-tokenize the command so quoted arguments stay intact
    (a `grep "git push"` doesn't look like a `git push`), split tokens
    at shell control operators into command segments, then check each
    segment's first token + arguments. This avoids the substring
    false-positives of regex-on-raw-string matching."""
    try:
        # Use shlex.shlex with punctuation_chars so operators glued to tokens
        # (`ls; rm` not `ls ; rm`, `cmd1|cmd2` not `cmd1 | cmd2`) split into
        # their own tokens. shlex.split does NOT do this — it only splits on
        # whitespace — and would let glued semicolons hide a destructive
        # second segment. Quoted strings still escape this: `echo "a;b"`
        # keeps `a;b` as one token.
        lex = shlex.shlex(command, posix=True, punctuation_chars="&|;")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        # Unparseable shell (unbalanced quotes etc.) — be safe and emit
        # nothing rather than a noisy false positive. The user can re-issue
        # the command if it was intended to trip the hook.
        return []

    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in SHELL_OPERATORS:
            segments.append([])
        else:
            segments[-1].append(tok)

    seen: set[str] = set()
    matches: list[str] = []
    for seg in segments:
        for label in _check_segment(seg):
            if label not in seen:
                seen.add(label)
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
