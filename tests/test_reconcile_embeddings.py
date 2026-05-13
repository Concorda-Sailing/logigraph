"""Integration test: logigraph reconcile embeds rule statements, domain
summaries, and process step descriptions."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "embed_fixture_logigraph"
REPO_ROOT = Path(__file__).resolve().parent.parent
RECONCILE = REPO_ROOT / "extractors" / "reconcile.py"

# lib.chunker and lib.embeddings live in depgraph's repo; fastembed + numpy
# live in depgraph's venv.  Use depgraph's interpreter so those packages are
# available.  reconcile.py's sys.path insertion ensures logigraph's lib/ is
# still reachable from that interpreter.
_DEPGRAPH_ROOT = REPO_ROOT.parent / "depgraph"
_DEPGRAPH_PYTHON = _DEPGRAPH_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(_DEPGRAPH_PYTHON) if _DEPGRAPH_PYTHON.exists() else sys.executable


def _setup_work(tmp_path: Path) -> Path:
    work = tmp_path / "logigraph"
    shutil.copytree(FIXTURE, work)
    return work


def test_reconcile_embeds_rule_domain_process(tmp_path):
    work = _setup_work(tmp_path)

    # Logigraph reconcile resolves its data dir from LOGIGRAPH_DATA_DIR.
    # DEPGRAPH_DATA_DIR points at a nonexistent dir — reconcile tolerates this
    # (prints a WARN) and continues; the embedding pass only needs logigraph nodes.
    env = {
        **os.environ,
        "LOGIGRAPH_DATA_DIR": str(work),
        "DEPGRAPH_DATA_DIR": str(tmp_path / "depgraph-stub"),
    }

    result = subprocess.run(
        [PYTHON, str(RECONCILE)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"reconcile failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    jsonl_path = work / "nodes" / "_index" / "embeddings.jsonl"
    assert jsonl_path.exists(), "embeddings.jsonl not written"

    rows = [json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()]

    # 1 rule statement + 1 domain summary + 2 process steps = 4 rows minimum
    assert len(rows) >= 4, f"expected ≥4 embedding rows, got {len(rows)}: {rows}"

    fields = {r["source_field"] for r in rows}
    assert "rule_statement" in fields, f"rule_statement missing from {fields}"
    assert "domain_summary" in fields, f"domain_summary missing from {fields}"
    assert "process_step" in fields, f"process_step missing from {fields}"

    required_keys = {"row", "node_id", "chunk_index", "content_hash", "text_preview", "source_field"}
    for r in rows:
        assert required_keys <= set(r.keys()), f"row missing keys: {required_keys - set(r.keys())} in {r}"

    meta = json.loads((work / "nodes" / "_meta.json").read_text())
    assert meta.get("embedding_status") == "ok", f"embedding_status={meta.get('embedding_status')!r}"
