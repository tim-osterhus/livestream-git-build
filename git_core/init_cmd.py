#!/usr/bin/env python3
"""`init` command implementation for repository surface scaffolding."""

from __future__ import annotations

from pathlib import Path

from repo import RepoPaths, discover_repo_paths
from refs import ensure_init_ref_layout


def _ensure_repo_surfaces(paths: RepoPaths) -> None:
    paths.git_dir.mkdir(parents=True, exist_ok=True)
    paths.objects_dir.mkdir(parents=True, exist_ok=True)
    ensure_init_ref_layout(paths)


def run_init(cwd: str | Path | None = None) -> int:
    """Create deterministic `.git` directory surfaces for the working tree."""

    paths = discover_repo_paths(cwd)
    _ensure_repo_surfaces(paths)
    print(f"Initialized empty Git repository in {paths.git_dir}")
    return 0
