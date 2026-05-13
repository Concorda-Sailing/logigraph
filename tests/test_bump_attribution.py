"""Tests for bump commands writing reviewed_by/reviewed_at and committing."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin" / "logigraph"


def _make_drafted_fixture(tmp_path: Path) -> Path:
    nodes = tmp_path / "nodes" / "rules"
    nodes.mkdir(parents=True)
    rule = {
        "schema_version": 2,
        "id": "rule::test::sample",
        "kind": "rule",
        "title": "Sample",
        "statement": "Sample.",
        "claims_code": [],
        "references_domain": [],
        "fan_out": 0,
        "definition_status": "llm_drafted",
        "dossier": "dossiers/rules/test__sample.md",
        "structural_hash": "deadbeef",
    }
    (nodes / "test__sample.json").write_text(json.dumps(rule, indent=2) + "\n")
    d = tmp_path / "dossiers" / "rules"
    d.mkdir(parents=True)
    (d / "test__sample.md").write_text(
        "---\n"
        "node_id: rule::test::sample\n"
        "node_kind: rule\n"
        "definition_status: llm_drafted\n"
        "authored_by:\n  - claude (opus-4.7)\n"
        "---\n\n"
        "## The rule\nBody.\n"
    )
    (tmp_path / "nodes" / "_index").mkdir()
    (tmp_path / "project.toml").write_text('[project]\nname = "test"\n')
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Logan"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def _run(args, data):
    env = {
        "LOGIGRAPH_DATA_DIR": str(data),
        "DEPGRAPH_DATA_DIR": str(data),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(data),
    }
    return subprocess.run([str(BIN), *args], cwd=data, env=env, capture_output=True, text=True)


def test_rule_bump_to_human_reviewed_writes_reviewed_by_and_at(tmp_path):
    data = _make_drafted_fixture(tmp_path)
    r = _run(["rule-bump", "rule::test::sample", "--status", "human_reviewed", "--actor", "logan"], data)
    assert r.returncode == 0, r.stderr
    dossier = (data / "dossiers/rules/test__sample.md").read_text()
    assert "reviewed_by: logan" in dossier
    assert "reviewed_at:" in dossier
    # authored_by preserved
    assert "claude (opus-4.7)" in dossier


def test_rule_bump_commits_with_review_prefix(tmp_path):
    data = _make_drafted_fixture(tmp_path)
    _run(["rule-bump", "rule::test::sample", "--status", "human_reviewed", "--actor", "logan"], data)
    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=data, capture_output=True, text=True
    )
    assert log.stdout.strip().startswith("review: rule::test::sample")


def test_rule_bump_back_to_llm_drafted_clears_reviewed_fields(tmp_path):
    data = _make_drafted_fixture(tmp_path)
    _run(["rule-bump", "rule::test::sample", "--status", "human_reviewed", "--actor", "logan"], data)
    _run(["rule-bump", "rule::test::sample", "--status", "llm_drafted", "--actor", "logan"], data)
    dossier = (data / "dossiers/rules/test__sample.md").read_text()
    assert "reviewed_by:" not in dossier
    assert "reviewed_at:" not in dossier
