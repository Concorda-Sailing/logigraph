"""Tests for bin/logigraph flag and unflag subcommands."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin" / "logigraph"


def _make_fixture(tmp_path: Path) -> Path:
    """Build a minimal logigraph data dir with one rule node, initialized as a git repo."""
    nodes = tmp_path / "nodes" / "rules"
    nodes.mkdir(parents=True)
    rule = {
        "schema_version": 2,
        "id": "rule::test::sample",
        "kind": "rule",
        "title": "Sample rule",
        "statement": "A sample rule for testing.",
        "claims_code": [],
        "references_domain": [],
        "fan_out": 0,
        "definition_status": "human_reviewed",
        "dossier": "dossiers/rules/test__sample.md",
        "structural_hash": "deadbeef",
    }
    (nodes / "test__sample.json").write_text(json.dumps(rule, indent=2) + "\n")
    dossier = tmp_path / "dossiers" / "rules"
    dossier.mkdir(parents=True)
    (dossier / "test__sample.md").write_text(
        "---\nnode_id: rule::test::sample\nnode_kind: rule\ndefinition_status: human_reviewed\n---\n\n## The rule\n\nSample body.\n"
    )
    (tmp_path / "nodes" / "_index").mkdir()
    (tmp_path / "project.toml").write_text('[project]\nname = "test"\n')
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def _run(args: list[str], data_dir: Path) -> subprocess.CompletedProcess:
    env = {
        "LOGIGRAPH_DATA_DIR": str(data_dir),
        "DEPGRAPH_DATA_DIR": str(data_dir),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(data_dir),
    }
    return subprocess.run(
        [str(BIN), *args],
        cwd=data_dir,
        env=env,
        capture_output=True,
        text=True,
    )


def test_flag_sets_node_fields_and_commits(tmp_path: Path):
    data = _make_fixture(tmp_path)
    r = _run(["flag", "rule::test::sample", "--reason", "perf issue", "--actor", "alice"], data)
    assert r.returncode == 0, r.stderr

    node = json.loads((data / "nodes/rules/test__sample.json").read_text())
    assert node["flagged"] is True
    assert node["flagged_by"] == "alice"
    assert node["flagged_at"]
    assert node.get("flagged_reason") == "perf issue"

    log = subprocess.run(
        ["git", "log", "-1", "--format=%s%n%b"], cwd=data, capture_output=True, text=True
    )
    assert log.stdout.startswith("flag: rule::test::sample")
    assert "perf issue" in log.stdout


def test_unflag_clears_node_fields_and_commits(tmp_path: Path):
    data = _make_fixture(tmp_path)
    _run(["flag", "rule::test::sample", "--reason", "x", "--actor", "alice"], data)
    r = _run(["unflag", "rule::test::sample", "--actor", "bob"], data)
    assert r.returncode == 0, r.stderr

    node = json.loads((data / "nodes/rules/test__sample.json").read_text())
    assert "flagged" not in node or node["flagged"] is False
    assert "flagged_by" not in node
    assert "flagged_at" not in node
    assert "flagged_reason" not in node

    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=data, capture_output=True, text=True
    )
    assert log.stdout.strip().startswith("unflag: rule::test::sample")


def test_flag_idempotent_with_same_actor_and_reason(tmp_path: Path):
    data = _make_fixture(tmp_path)
    _run(["flag", "rule::test::sample", "--reason", "x", "--actor", "alice"], data)
    before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=data, capture_output=True, text=True
    ).stdout.strip()
    _run(["flag", "rule::test::sample", "--reason", "x", "--actor", "alice"], data)
    after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=data, capture_output=True, text=True
    ).stdout.strip()
    assert before == after


def test_flag_unknown_id_exits_1(tmp_path: Path):
    data = _make_fixture(tmp_path)
    r = _run(["flag", "rule::test::no_such", "--reason", "x"], data)
    assert r.returncode == 1
    assert "no" in r.stderr.lower()
