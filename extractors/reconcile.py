#!/usr/bin/env python3
"""
reconcile.py — second-pass for the logigraph after node authoring or
extractor runs.

Responsibilities, in order:

  1. Load every logigraph node JSON in nodes/{domain,rules}/**/*.json.
  2. Load the depgraph corpus once, keyed by id, so claims can be
     validated and remote_hash can be refreshed.
  3. For each rule, refresh `claims_code[].remote_hash` from the current
     depgraph node and set `stale: true` when divergent. Validate that
     every claim's `depgraph_id` exists in the depgraph corpus —
     missing ids fail loud.
  4. Validate every rule's `references_domain` against the local
     domain corpus. Missing ids fail loud.
  5. Compute `fan_out` on each rule (count of claims_code).
  6. Write three reverse-edge indexes atomically:
       _index/by_code.json       depgraph_id → [rule_ids]
       _index/by_file.json       repo/path   → [rule_ids]
       _index/by_domain.json   domain_id → [rule_ids]
  7. Write _meta.json with regen_status: complete (clearing the
     in_progress marker that bin/logigraph set at regen start).

Pure functions where practical. Atomic writes (tmp+rename). Bit-stable:
two consecutive regens with no source changes produce zero file diffs.

Phase 0 scope: rules and domain are *authored*, not extracted.
Manifests for domain extractors will come in Phase 1
(extract_system_roles.py, extract_db_resources.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_ROOT))
from lib.config import resolve_data_dir, primary_repo_path, load_project_config  # noqa: E402

LOGIGRAPH = resolve_data_dir("LOGIGRAPH_DATA_DIR")


def _depgraph_dir() -> Path:
    """Logigraph claims against a depgraph corpus. Source priority:
       1. DEPGRAPH_DATA_DIR env var
       2. [depgraph].data_dir from logigraph's project.toml
       3. SystemExit (caller can't proceed without it)
    """
    env = os.environ.get("DEPGRAPH_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    cfg = load_project_config(LOGIGRAPH)
    dg = (cfg.get("depgraph") or {}).get("data_dir")
    if dg:
        return Path(dg).expanduser().resolve()
    raise SystemExit(
        "Cannot locate depgraph data dir: set DEPGRAPH_DATA_DIR or add "
        "[depgraph] data_dir = \"...\" to logigraph's project.toml."
    )


DEPGRAPH = _depgraph_dir()
NODES = LOGIGRAPH / "nodes"
INDEX_DIR = NODES / "_index"
BY_CODE_INDEX = INDEX_DIR / "by_code.json"
BY_FILE_INDEX = INDEX_DIR / "by_file.json"
BY_DOMAIN_INDEX = INDEX_DIR / "by_domain.json"
CORPUS_META = NODES / "_meta.json"
INDEX_SCHEMA_VERSION = 1
META_SCHEMA_VERSION = 1


def _is_node_file(path: Path) -> bool:
    if path.name.startswith("_"):
        return False
    if any(p.startswith("_") for p in path.parts):
        return False
    return True


def load_all_nodes() -> dict[str, tuple[Path, dict]]:
    out: dict[str, tuple[Path, dict]] = {}
    for path in NODES.rglob("*.json"):
        if not _is_node_file(path):
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"WARN: invalid JSON {path}: {e}", file=sys.stderr)
            continue
        nid = data.get("id")
        if not nid:
            continue
        out[nid] = (path, data)
    return out


def load_depgraph_corpus() -> dict[str, dict]:
    """Load every depgraph node JSON, keyed by id. Returns empty dict if
    the depgraph isn't initialized — reconcile will then fail rules' claim
    validation, which is the right behavior."""
    by_id: dict[str, dict] = {}
    dnodes = DEPGRAPH / "nodes"
    if not dnodes.exists():
        print(f"WARN: depgraph not found at {DEPGRAPH}", file=sys.stderr)
        return by_id
    for path in dnodes.rglob("*.json"):
        if path.name.startswith("_") or any(p.startswith("_") for p in path.parts):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        nid = data.get("id")
        if nid:
            by_id[nid] = data
    return by_id


def refresh_claims_and_validate(
    nodes: dict[str, tuple[Path, dict]],
    depgraph_corpus: dict[str, dict],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """For every rule:
      - Refresh remote_hash from current depgraph and toggle stale flag.
      - Compute fan_out from claims_code.
      - Collect orphan claims (claim_id not in depgraph corpus).
      - Collect orphan domain refs (referenced domain id not authored).
      - Collect stale claims (remote_hash diverged from current).

    Mutates the loaded node dicts in place. Returns the three orphan lists
    for reporting.
    """
    domain_ids = {nid for nid, (_, d) in nodes.items() if d.get("kind") == "domain"}

    orphan_claims: list[tuple[str, str]] = []
    orphan_domain: list[tuple[str, str]] = []
    stale_claims: list[tuple[str, str]] = []

    for rid, (_, data) in nodes.items():
        if data.get("kind") != "rule":
            continue
        for claim in data.get("claims_code", []):
            cid = claim.get("depgraph_id")
            if not cid:
                continue
            depnode = depgraph_corpus.get(cid)
            if depnode is None:
                orphan_claims.append((rid, cid))
                claim["stale"] = True
                continue
            current_hash = depnode.get("structural_hash")
            stored_hash = claim.get("remote_hash")
            if stored_hash and current_hash and stored_hash != current_hash:
                claim["stale"] = True
                stale_claims.append((rid, cid))
            else:
                claim["stale"] = False
            # Refresh remote_hash on every regen so subsequent runs detect drift.
            if current_hash:
                claim["remote_hash"] = current_hash
        data["fan_out"] = len(data.get("claims_code", []))

        for ref in data.get("references_domain", []):
            if ref not in domain_ids:
                orphan_domain.append((rid, ref))

    return orphan_claims, stale_claims, orphan_domain


def write_node_if_changed(path: Path, data: dict) -> bool:
    """Write data to path only if the canonical JSON differs from disk.
    Returns True if a write occurred."""
    new_text = json.dumps(data, indent=2, sort_keys=False) + "\n"
    if path.exists():
        try:
            existing = path.read_text()
            if existing == new_text:
                return False
        except OSError:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text)
    tmp.replace(path)
    return True


def persist_node_updates(nodes: dict[str, tuple[Path, dict]]) -> int:
    """Write back any nodes whose claim hashes / fan_out changed."""
    n = 0
    for nid, (path, data) in nodes.items():
        if write_node_if_changed(path, data):
            n += 1
    return n


def build_indexes(
    nodes: dict[str, tuple[Path, dict]],
    depgraph_corpus: dict[str, dict],
) -> tuple[dict, dict, dict]:
    """Build the three reverse-edge indexes. Pure: returns three dicts ready
    to serialize."""
    by_code: dict[str, list[str]] = {}
    by_file: dict[str, list[str]] = {}
    by_domain: dict[str, list[str]] = {}

    for rid, (_, data) in nodes.items():
        if data.get("kind") != "rule":
            continue
        for claim in data.get("claims_code", []):
            cid = claim.get("depgraph_id")
            if not cid:
                continue
            by_code.setdefault(cid, []).append(rid)
            depnode = depgraph_corpus.get(cid)
            if depnode:
                src = depnode.get("source") or {}
                repo = src.get("repo")
                rel = src.get("path")
                if repo and rel:
                    key = f"{repo}/{rel}"
                    if rid not in by_file.setdefault(key, []):
                        by_file[key].append(rid)
        for ref in data.get("references_domain", []):
            by_domain.setdefault(ref, []).append(rid)

    # Sort lists deterministically so indexes are bit-stable.
    for d in (by_code, by_file, by_domain):
        for k in d:
            d[k] = sorted(set(d[k]))

    # Sort dict keys for deterministic serialization.
    return (
        {k: by_code[k] for k in sorted(by_code)},
        {k: by_file[k] for k in sorted(by_file)},
        {k: by_domain[k] for k in sorted(by_domain)},
    )


def _git_head_primary() -> str | None:
    """Return the first 12 chars of the primary repo's git HEAD, or None.
    Primary repo is determined by [project] primary_repo in project.toml,
    falling back to the first [repos.*] table."""
    repo_path = primary_repo_path(LOGIGRAPH)
    if repo_path is None:
        return None
    head = repo_path / ".git" / "HEAD"
    if not head.exists():
        return None
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            ref_path = repo_path / ".git" / ref.split(" ", 1)[1]
            if ref_path.exists():
                return ref_path.read_text().strip()[:12]
        return ref[:12]
    except OSError:
        return None


def _write_index(path: Path, payload: dict, stable_excludes: tuple[str, ...] = ("generated_at",)) -> bool:
    """Atomic write with bit-stability: skip the rewrite if existing content
    matches new content modulo timestamp fields."""
    new_text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            existing_stable = {k: v for k, v in existing.items() if k not in stable_excludes}
            new_stable = {k: v for k, v in payload.items() if k not in stable_excludes}
            if existing_stable == new_stable:
                return False
        except (OSError, json.JSONDecodeError):
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text)
    tmp.replace(path)
    return True


def write_indexes(by_code: dict, by_file: dict, by_domain: dict, rule_count: int) -> tuple[bool, bool, bool]:
    """Write the three reverse-edge index files. Returns (changed_code,
    changed_file, changed_domain)."""
    now = datetime.now(timezone.utc).isoformat()
    git = _git_head_primary()

    code_payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": now,
        "git_commit": git,
        "rule_count": rule_count,
        "target_count": len(by_code),
        "by_target": by_code,
    }
    file_payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": now,
        "git_commit": git,
        "rule_count": rule_count,
        "file_count": len(by_file),
        "by_file": by_file,
    }
    domain_payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": now,
        "git_commit": git,
        "rule_count": rule_count,
        "domain_count": len(by_domain),
        "by_domain": by_domain,
    }
    c1 = _write_index(BY_CODE_INDEX, code_payload)
    c2 = _write_index(BY_FILE_INDEX, file_payload)
    c3 = _write_index(BY_DOMAIN_INDEX, domain_payload)
    return c1, c2, c3


def write_corpus_meta(node_count: int, rule_count: int, domain_count: int) -> bool:
    """Flip regen_status to complete. Bit-stable on no-op regens."""
    payload = {
        "schema_version": META_SCHEMA_VERSION,
        "regen_status": "complete",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head_primary(),
        "node_count": node_count,
        "rule_count": rule_count,
        "domain_count": domain_count,
    }
    return _write_index(CORPUS_META, payload, stable_excludes=("generated_at", "started_at"))


def detect_mediation_collisions(nodes: dict) -> list[tuple[str, list[str]]]:
    """Group relationship entities by `mediated_by`. Any group with more
    than one distinct relationship id is a *mediation collision*: two
    conceptually-distinct relationships sharing the same storage / join /
    predicate. That shared storage is the smoke signal for a domain
    category error — e.g. ownership and crew membership both stored in
    boat_crew.

    Returns: list of (mediated_by, [relationship_ids]) for groups with
    >1 distinct relationships.
    """
    by_mech: dict[str, list[str]] = {}
    for nid, (_path, data) in nodes.items():
        if data.get("kind") != "domain":
            continue
        if data.get("subkind") != "relationship":
            continue
        mech = data.get("mediated_by")
        if not mech:
            continue
        # Normalize: strip parenthetical qualifiers so 'boat_crew (role=owner)'
        # and 'boat_crew (role=crew)' both bucket as 'boat_crew'. The
        # qualifier is exactly what distinguishes the use — collision is the
        # point.
        head = mech.split("(", 1)[0].strip().rstrip(",").lower()
        # If multiple mechanisms are listed ('A and B'), bucket under each.
        for piece in [p.strip() for p in head.split(" and ")]:
            if not piece:
                continue
            by_mech.setdefault(piece, []).append(nid)
    return [(m, sorted(ids)) for m, ids in sorted(by_mech.items()) if len(set(ids)) > 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if any orphans/stale claims found.")
    args = parser.parse_args()

    nodes = load_all_nodes()
    depgraph_corpus = load_depgraph_corpus()

    orphan_claims, stale_claims, orphan_domain = refresh_claims_and_validate(
        nodes, depgraph_corpus
    )

    rule_count = sum(1 for _, (_, d) in nodes.items() if d.get("kind") == "rule")
    domain_count = sum(1 for _, (_, d) in nodes.items() if d.get("kind") == "domain")

    if not args.report_only:
        node_writes = persist_node_updates(nodes)
    else:
        node_writes = 0

    by_code, by_file, by_domain = build_indexes(nodes, depgraph_corpus)

    if not args.report_only:
        c_code, c_file, c_ont = write_indexes(by_code, by_file, by_domain, rule_count)
        meta_changed = write_corpus_meta(len(nodes), rule_count, domain_count)
    else:
        c_code = c_file = c_ont = meta_changed = False

    print(f"loaded:           {len(nodes)} logigraph nodes ({rule_count} rules, {domain_count} domain)")
    print(f"depgraph corpus:  {len(depgraph_corpus)} nodes")
    print(f"node updates:     {node_writes} (claim hash / fan_out refresh)")
    print(f"index changes:    by_code={'updated' if c_code else 'unchanged'}, by_file={'updated' if c_file else 'unchanged'}, by_domain={'updated' if c_ont else 'unchanged'}")
    print(f"meta:             {'updated' if meta_changed else 'unchanged'}")
    print(f"orphan claims:    {len(orphan_claims)}")
    for rid, cid in orphan_claims[:10]:
        print(f"  {rid} → {cid}")
    if len(orphan_claims) > 10:
        print(f"  ... and {len(orphan_claims) - 10} more")
    print(f"orphan domain:  {len(orphan_domain)}")
    for rid, ref in orphan_domain[:10]:
        print(f"  {rid} → {ref}")
    if len(orphan_domain) > 10:
        print(f"  ... and {len(orphan_domain) - 10} more")
    print(f"stale claims:     {len(stale_claims)}")
    for rid, cid in stale_claims[:10]:
        print(f"  {rid} → {cid}")
    if len(stale_claims) > 10:
        print(f"  ... and {len(stale_claims) - 10} more")

    collisions = detect_mediation_collisions(nodes)
    print(f"mediation coll.:  {len(collisions)}")
    for mech, ids in collisions:
        print(f"  ⚠ `{mech}` mediates {len(ids)} distinct relationships:")
        for rid in ids:
            print(f"      - {rid}")

    if args.strict and (orphan_claims or orphan_domain):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
