#!/usr/bin/env python3
"""
post_edit_telemetry.py — Claude Code Stop hook for logigraph telemetry.

At session end, scans the session transcript for mentions of rule IDs
or rule titles that were injected during the session, and writes
acknowledgment events to telemetry/acknowledgments.jsonl. Combined with
the injection log written by pre_edit_inject.py, this lets us answer:
"is rule X's prose actually changing reasoning, or are we just shouting
into the void?"

Acknowledgment is a soft signal — the LLM mentioning a rule by name
does not prove the rule influenced the decision, only that it was
read and processed. The opposite (rule injected, never mentioned) is a
stronger signal: prose worth re-reviewing.

Failure modes:
  - No transcript_path in payload → silent exit 0.
  - Transcript file missing → silent exit 0.
  - Telemetry write failure → silent swallow (telemetry must not block).
  - Any unhandled exception → silent exit 0 (Stop hooks must never
    error out and break session close).

Time window: scans injections from the last 6 hours (rough proxy for
"current session"). Could be tightened with a session_id from the
harness if/when one becomes available.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

LOGIGRAPH = Path(os.environ.get("CONCORDA_LOGIGRAPH_PATH", Path.home() / "concorda" / "logigraph")).resolve()
TELEMETRY_DIR = LOGIGRAPH / "telemetry"
INJECTIONS_LOG = TELEMETRY_DIR / "injections.jsonl"
ACKS_LOG = TELEMETRY_DIR / "acknowledgments.jsonl"
RULES_DIR = LOGIGRAPH / "nodes" / "rules"

SESSION_WINDOW_HOURS = 6


def _silent_exit(rc: int = 0) -> None:
    sys.exit(rc)


def _load_recent_injections() -> list[dict]:
    """Return injection events from the last SESSION_WINDOW_HOURS, parsed."""
    if not INJECTIONS_LOG.exists():
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=SESSION_WINDOW_HOURS)
    out: list[dict] = []
    try:
        with INJECTIONS_LOG.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = ev.get("ts")
                if not ts_str:
                    continue
                try:
                    ts = dt.datetime.fromisoformat(ts_str)
                except ValueError:
                    continue
                if ts >= cutoff:
                    out.append(ev)
    except OSError:
        return []
    return out


def _rule_titles_for(rule_ids: set[str]) -> dict[str, str]:
    """Return {rule_id: title} for the given ids by reading rule node JSON.
    Used to also match on natural-language title mentions, not just id."""
    titles: dict[str, str] = {}
    if not RULES_DIR.exists():
        return titles
    for path in RULES_DIR.rglob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rid = data.get("id")
        if rid in rule_ids and data.get("title"):
            titles[rid] = data["title"]
    return titles


def _read_transcript(transcript_path: str) -> str:
    """Return the concatenated text content of all assistant messages from
    the transcript file. Transcript is JSONL with one message per line."""
    if not transcript_path:
        return ""
    p = Path(transcript_path)
    if not p.exists():
        return ""
    parts: list[str] = []
    try:
        with p.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Different transcript formats; handle both nested
                # "message.content" and flat "content".
                content = msg.get("message", {}).get("content") or msg.get("content")
                role = (msg.get("message", {}).get("role") or msg.get("role") or "").lower()
                if role and role != "assistant":
                    continue
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") in ("text", "thinking"):
                            t = block.get("text") or block.get("thinking") or ""
                            if t:
                                parts.append(t)
    except OSError:
        return ""
    return "\n".join(parts)


def _record_acknowledgment(rule_id: str, matched_phrase: str) -> None:
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        with ACKS_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "kind": "acknowledgment",
                "rule_id": rule_id,
                "matched_phrase": matched_phrase[:120],  # truncate for log volume
            }) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        _silent_exit(0)

    transcript_path = payload.get("transcript_path", "")
    transcript = _read_transcript(transcript_path)
    if not transcript:
        _silent_exit(0)

    injections = _load_recent_injections()
    if not injections:
        _silent_exit(0)

    candidate_rule_ids = {ev.get("rule_id") for ev in injections if ev.get("rule_id")}
    titles = _rule_titles_for(candidate_rule_ids)

    # For each candidate rule, check whether the transcript mentions either
    # the id (precise) or the title (looser, but tolerant of natural-prose
    # references). One acknowledgment per matched rule per session.
    acknowledged: set[str] = set()
    for rid in candidate_rule_ids:
        if rid in transcript:
            _record_acknowledgment(rid, rid)
            acknowledged.add(rid)
            continue
        title = titles.get(rid, "")
        if title and len(title) > 12 and title in transcript:
            _record_acknowledgment(rid, title)
            acknowledged.add(rid)

    # Stop hook output is optional; if we want to surface a session-end
    # summary in stdout, the harness will display it. Keep it terse.
    if acknowledged:
        # additionalContext on Stop is shown to the user, not the model;
        # use sparingly.
        pass

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Stop hooks must never break session close. Swallow everything.
        sys.exit(0)
