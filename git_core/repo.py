#!/usr/bin/env python3
"""Repository path discovery helpers for the staged git implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoPaths:
    """Deterministic repository surface paths for a working tree."""

    worktree: Path
    git_dir: Path
    objects_dir: Path
    refs_dir: Path
    heads_dir: Path
    tags_dir: Path
    head_file: Path

    def ref_path(self, ref_name: str) -> Path:
        """Resolve a full git ref name (for example `refs/heads/main`) to disk path."""

        return self.git_dir / ref_name

    def branch_ref_path(self, branch_name: str) -> Path:
        """Resolve a branch short name to `.git/refs/heads/<name>`."""

        return self.heads_dir / branch_name

    def tag_ref_path(self, tag_name: str) -> Path:
        """Resolve a tag short name to `.git/refs/tags/<name>`."""

        return self.tags_dir / tag_name


def discover_repo_paths(cwd: str | Path | None = None) -> RepoPaths:
    """Resolve absolute repository paths from the given or current directory."""

    worktree = Path(cwd) if cwd is not None else Path.cwd()
    worktree = worktree.resolve()
    git_dir = worktree / ".git"
    refs_dir = git_dir / "refs"

    return RepoPaths(
        worktree=worktree,
        git_dir=git_dir,
        objects_dir=git_dir / "objects",
        refs_dir=refs_dir,
        heads_dir=refs_dir / "heads",
        tags_dir=refs_dir / "tags",
        head_file=git_dir / "HEAD",
    )
