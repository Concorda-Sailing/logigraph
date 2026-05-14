#!/usr/bin/env python3
"""
post_edit_regen.py — Stop hook for logigraph.

Runs `bin/logigraph regen` after a turn ends. Unlike depgraph's per-file
extractor pass, logigraph's reconcile always operates over the whole
corpus: it refreshes claim remote_hash values from the current depgraph,
re-counts fan_out, validates orphan claim/domain refs, and (cheaply, via
content hashing) regenerates the semantic embedding index over rule
statements, domain summaries, and process step titles.

Wire-up in ~/.claude/settings.json:

  {
    "hooks": {
      "Stop": [{
        "hooks": [{
          "type": "command",
          "command": "LOGIGRAPH_DATA_DIR=<corpus> DEPGRAPH_DATA_DIR=<corpus> python3 ~/tools/knowledge-graph/logigraph/hooks/post_edit_regen.py"
        }]
      }]
    }
  }

Design notes:

  • Best-effort: any failure is logged into the systemMessage but never
    blocks the Stop hook from completing.
  • Output is suppressed when regen reports no changes — the most common
    case (turns that touch unrelated files) emits nothing.
  • Pairs with depgraph's post_edit_regen.py; the two cover the framework's
    dual corpora. Without this companion, logigraph's semantic index drifts
    behind any rule/process additions until someone runs `logigraph regen`
    manually.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent.parent


def emit(envelope: dict) -> None:
    json.dump(envelope, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_message(msg: str) -> None:
    emit({"systemMessage": msg})


def main() -> int:
    # We don't actually need the payload; reading stdin only to drain it
    # so Claude Code doesn't see a "hook didn't consume input" warning.
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        pass

    # Run `bin/logigraph regen`. Inherits LOGIGRAPH_DATA_DIR /
    # DEPGRAPH_DATA_DIR from the env the hook was invoked with.
    bin_logigraph = TOOL_ROOT / "bin" / "logigraph"
    proc = subprocess.run(
        [sys.executable, str(bin_logigraph), "regen"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    # Decide whether to surface anything. The regen prints a multi-line
    # summary; we only emit when something actually changed (node updates,
    # index changes, orphans, stale claims) OR when regen failed.
    if proc.returncode != 0:
        emit_message(f"⚠ logigraph regen failed: {err[:600] or output[:600]}")
        return 0

    interesting_markers = (
        "node updates:",
        "orphan claims:",
        "orphan domain:",
        "stale claims:",
        "mediation coll.:",
        "by_code=updated",
        "by_file=updated",
        "by_domain=updated",
    )
    keep = [line for line in output.splitlines()
            if any(m in line for m in interesting_markers)]
    # Filter out the boring "0 / unchanged / 0 / 0" version
    notable = [line for line in keep
               if not (line.endswith(": 0") or "unchanged" in line)]
    if not notable:
        return 0

    msg_lines = ["## 🧭 logigraph regen", ""]
    msg_lines.append("```")
    msg_lines.extend(output.splitlines()[:25])
    msg_lines.append("```")
    emit_message("\n".join(msg_lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        emit_message(f"⚠ logigraph post-edit hook crashed: {type(e).__name__}: {e}")
        sys.exit(0)
