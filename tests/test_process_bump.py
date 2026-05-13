"""End-to-end test for `logigraph process-bump`.

Runs the CLI as a subprocess against a temporary corpus to avoid
polluting any real instance. Asserts that both the node JSON and
the dossier frontmatter pick up the new status.
"""
import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

LOGIGRAPH_BIN = Path(__file__).resolve().parents[1] / "bin" / "logigraph"


@pytest.fixture
def temp_corpus(tmp_path: Path) -> Path:
    """Build a minimal logigraph corpus with one process node + dossier."""
    (tmp_path / "nodes" / "processes").mkdir(parents=True)
    (tmp_path / "dossiers" / "processes").mkdir(parents=True)
    (tmp_path / "nodes" / "rules").mkdir(parents=True)
    (tmp_path / "nodes" / "domain").mkdir(parents=True)
    (tmp_path / "nodes" / "_index").mkdir(parents=True)
    (tmp_path / "project.toml").write_text(
        '[project]\nname = "test"\n[depgraph]\ndata_dir = "/tmp/nonexistent"\n'
    )
    node = {
        "schema_version": 2,
        "id": "process::testing::sample_proc",
        "kind": "process",
        "title": "Sample test process",
        "definition_status": "llm_drafted",
        "structural_hash": "abc123sample",
        "dossier": "dossiers/processes/testing__sample_proc.md",
    }
    (tmp_path / "nodes" / "processes" / "testing__sample_proc.json").write_text(
        json.dumps(node, indent=2) + "\n"
    )
    (tmp_path / "dossiers" / "processes" / "testing__sample_proc.md").write_text(textwrap.dedent("""\
        ---
        node_id: process::testing::sample_proc
        node_kind: process
        definition_status: llm_drafted
        last_reviewed: 2026-01-01
        last_reviewed_against_hash: abc123sample
        ---

        # Sample test process

        ## The process

        Body content.
        """))
    return tmp_path


def _run_cli(corpus: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["LOGIGRAPH_DATA_DIR"] = str(corpus)
    return subprocess.run(
        [str(LOGIGRAPH_BIN), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_process_bump_promotes_to_human_reviewed(temp_corpus: Path):
    result = _run_cli(temp_corpus, "process-bump", "process::testing::sample_proc")
    assert result.returncode == 0, result.stderr
    node = json.loads((temp_corpus / "nodes" / "processes" / "testing__sample_proc.json").read_text())
    assert node["definition_status"] == "human_reviewed"
    dossier = (temp_corpus / "dossiers" / "processes" / "testing__sample_proc.md").read_text()
    assert "definition_status: human_reviewed" in dossier
    # Frontmatter rewrite must preserve hash + bump last_reviewed to today.
    assert "last_reviewed_against_hash: abc123sample" in dossier
    assert "last_reviewed: 2026-01-01" not in dossier  # date got bumped


def test_process_bump_explicit_status(temp_corpus: Path):
    result = _run_cli(temp_corpus, "process-bump", "process::testing::sample_proc",
                      "--status", "llm_drafted")
    assert result.returncode == 0, result.stderr
    node = json.loads((temp_corpus / "nodes" / "processes" / "testing__sample_proc.json").read_text())
    assert node["definition_status"] == "llm_drafted"


def test_process_bump_unknown_id_errors(temp_corpus: Path):
    result = _run_cli(temp_corpus, "process-bump", "process::testing::nonexistent")
    assert result.returncode != 0
    assert "no process node" in result.stderr


def test_process_bump_rejects_bad_id_shape(temp_corpus: Path):
    result = _run_cli(temp_corpus, "process-bump", "rule::testing::wrongkind")
    assert result.returncode != 0
    assert "not a valid process id" in result.stderr
