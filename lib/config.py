"""Shared project-config parser for the depgraph framework.

All scripts in `bin/`, `hooks/`, and `extractors/` read project.toml
through this module so the schema is enforced in one place.

Schema (per-repo tables, mandatory):

    [project]
    name = "..."
    primary_repo = "<key>"   # optional; falls back to first [repos.*] key

    [repos.<key>]
    path = "~/<dir>"                                     # required
    extractor = ["python3", "{data_dir}/extractors/x.py"] # optional list
    files_arg = "--only"                                  # optional str

Substitutions available in `extractor` tokens:
    {data_dir}  — the framework data dir (e.g. ~/concorda/depgraph)
    {path}      — the repo's resolved path
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_data_dir(env_var: str) -> Path:
    """Resolve a graph data dir. Priority:
       1. `env_var` (e.g. DEPGRAPH_DATA_DIR) — explicit override.
       2. Walk up from cwd looking for `project.toml` next to `nodes/`.
       3. Raise SystemExit with a helpful message.

    Hooks always set the env var explicitly; CLI users either export it
    or cd into a project dir.
    """
    explicit = os.environ.get(env_var)
    if explicit:
        return Path(explicit).expanduser().resolve()
    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        if (d / "project.toml").exists() and (d / "nodes").is_dir():
            return d
    raise SystemExit(
        f"{env_var} is not set and no project root found in cwd or ancestors. "
        f"Either export {env_var}=/path/to/project/data, or cd into a "
        f"directory containing project.toml + nodes/."
    )


def _load_tomllib():
    try:
        import tomllib  # py311+
        return tomllib
    except ImportError:
        try:
            import tomli  # type: ignore
            return tomli
        except ImportError:
            return None


def load_project_config(data_dir: Path) -> dict:
    """Read project.toml from `data_dir/project.toml` (or one level up).
    Returns {} if missing or unparseable."""
    candidates = [data_dir / "project.toml", data_dir.parent / "project.toml"]
    tomllib = _load_tomllib()
    if tomllib is None:
        return {}
    for cfg in candidates:
        if not cfg.exists():
            continue
        try:
            return tomllib.loads(cfg.read_text())
        except Exception:
            return {}
    return {}


def project_repos(data_dir: Path) -> dict[str, dict]:
    """Parse [repos.<key>] tables into a normalized dict.

    Returns: {repo_key: {"path": Path, "basename": str,
                         "extractor": list[str] | None,
                         "files_arg": str | None}}

    The repo_key is the [repos.<key>] table name (e.g. "api").
    The basename is the final path segment (e.g. "concorda-api"), used
    for home-relative path matching when classifying file paths.

    Raises ValueError if [repos.*] is present but malformed.
    Returns {} if no [repos.*] tables are configured.
    """
    cfg = load_project_config(data_dir)
    repos_raw = cfg.get("repos") or {}
    out: dict[str, dict] = {}
    for key, val in repos_raw.items():
        if not isinstance(val, dict):
            raise ValueError(
                f"project.toml [repos.{key}] must be a table with `path`, "
                f"got a bare value. Per-repo tables are required."
            )
        path = val.get("path")
        if not path:
            raise ValueError(f"project.toml [repos.{key}] missing `path`")
        resolved = Path(path).expanduser().resolve()
        out[key] = {
            "path": resolved,
            "basename": resolved.name,
            "extractor": val.get("extractor"),
            "files_arg": val.get("files_arg"),
        }
    return out


def project_primary_repo(data_dir: Path) -> Optional[str]:
    """Return the repo_key whose git HEAD stamps the corpus-meta git_commit
    field. Falls back to the first [repos.*] key. Returns None if no repos
    are configured."""
    cfg = load_project_config(data_dir)
    proj = cfg.get("project") or {}
    primary = proj.get("primary_repo")
    repos = project_repos(data_dir)
    if primary and primary in repos:
        return primary
    if repos:
        return next(iter(repos))
    return None


def primary_repo_path(data_dir: Path) -> Optional[Path]:
    """Convenience: resolve the primary repo's path. Used by git-head stampers."""
    key = project_primary_repo(data_dir)
    if key is None:
        return None
    return project_repos(data_dir)[key]["path"]


def render_extractor(repo_info: dict, data_dir: Path) -> Optional[list[str]]:
    """Apply {data_dir}/{path} substitutions to the extractor token list.
    Returns None if the repo has no extractor configured."""
    extractor = repo_info.get("extractor")
    if not extractor:
        return None
    subs = {
        "data_dir": str(data_dir),
        "path": str(repo_info["path"]),
    }
    return [token.format(**subs) for token in extractor]


def repo_basenames(data_dir: Path) -> set[str]:
    """Convenience: the set of repo basenames, for path-matching like
    `seg == basename` in place of the old `seg.startswith('concorda')`."""
    return {r["basename"] for r in project_repos(data_dir).values()}


def repo_for_basename(data_dir: Path, basename: str) -> Optional[dict]:
    """Look up a repo_info by its basename (e.g. 'concorda-api')."""
    for info in project_repos(data_dir).values():
        if info["basename"] == basename:
            return info
    return None
