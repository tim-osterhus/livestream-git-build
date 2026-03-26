#!/usr/bin/env python3
"""`init` command implementation for repository surface scaffolding."""

from __future__ import annotations

from pathlib import Path

from repo import RepoPaths, discover_repo_paths

DEFAULT_HEAD_REF = "refs/heads/main"


def _ensure_repo_surfaces(paths: RepoPaths) -> None:
    paths.git_dir.mkdir(parents=True, exist_ok=True)
    paths.objects_dir.mkdir(parents=True, exist_ok=True)
    paths.refs_dir.mkdir(parents=True, exist_ok=True)
    paths.heads_dir.mkdir(parents=True, exist_ok=True)
    paths.tags_dir.mkdir(parents=True, exist_ok=True)

    if not paths.head_file.exists():
        paths.head_file.write_text(f"ref: {DEFAULT_HEAD_REF}\n", encoding="utf-8")


def run_init(cwd: str | Path | None = None) -> int:
    """Create deterministic `.git` directory surfaces for the working tree."""

    paths = discover_repo_paths(cwd)
    _ensure_repo_surfaces(paths)
    print(f"Initialized empty Git repository in {paths.git_dir}")
    return 0
