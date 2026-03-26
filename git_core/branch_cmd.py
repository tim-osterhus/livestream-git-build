#!/usr/bin/env python3
"""`branch` command implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

from refs import persist_ref_atomic, read_branch_tip_by_name, read_head_commit_oid
from repo import discover_repo_paths

BRANCH_USAGE = "usage: run_git branch <name>\n"


def _print_usage(stream: object) -> None:
    stream.write(BRANCH_USAGE)


def _parse_branch_args(args: Sequence[str]) -> str:
    if len(args) != 1:
        raise ValueError("branch requires exactly '<name>'")
    if not args[0]:
        raise ValueError("branch name must not be empty")
    return args[0]


def run_branch(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Create `refs/heads/<name>` pointing at the current HEAD commit."""

    try:
        branch_name = _parse_branch_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: branch: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: branch: not a git repository (missing .git).\n")
        return 1

    try:
        read_branch_tip_by_name(repo_paths, branch_name)
        head_oid = read_head_commit_oid(repo_paths.head_file, repo_paths.git_dir)
    except ValueError as exc:
        sys.stderr.write(f"run_git: branch: {exc}\n")
        return 1

    if head_oid is None:
        sys.stderr.write("run_git: branch: HEAD does not point to a commit.\n")
        return 1

    try:
        persist_ref_atomic(repo_paths.branch_ref_path(branch_name), head_oid)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"run_git: branch: unable to update branch ref: {exc}\n")
        return 1

    return 0
