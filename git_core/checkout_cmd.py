#!/usr/bin/env python3
"""`checkout` command implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence
import zlib

from refs import (
    persist_head_symbolic_ref_atomic,
    read_branch_tip_by_name,
    read_head_commit_oid,
)
from repo import discover_repo_paths
from tree_checkout import materialize_commit_checkout

CHECKOUT_USAGE = "usage: run_git checkout <name>\n"


def _print_usage(stream: object) -> None:
    stream.write(CHECKOUT_USAGE)


def _parse_checkout_args(args: Sequence[str]) -> str:
    if len(args) != 1:
        raise ValueError("checkout requires exactly '<name>'")
    if not args[0]:
        raise ValueError("branch name must not be empty")
    return args[0]


def run_checkout(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Switch HEAD to target branch and materialize its commit tree."""

    try:
        branch_name = _parse_checkout_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: checkout: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: checkout: not a git repository (missing .git).\n")
        return 1

    branch_ref_path = repo_paths.branch_ref_path(branch_name)
    branch_ref_name = f"refs/heads/{branch_name}"

    try:
        target_oid = read_branch_tip_by_name(repo_paths, branch_name)
        current_oid = read_head_commit_oid(repo_paths.head_file, repo_paths.git_dir)
    except ValueError as exc:
        sys.stderr.write(f"run_git: checkout: {exc}\n")
        return 1

    if target_oid is None:
        if branch_ref_path.exists():
            sys.stderr.write(
                f"run_git: checkout: branch '{branch_name}' does not point to a commit.\n"
            )
        else:
            sys.stderr.write(f"run_git: checkout: unknown branch '{branch_name}'.\n")
        return 1

    try:
        materialize_commit_checkout(repo_paths, target_oid, current_oid)
    except (ValueError, OSError, RuntimeError, EOFError, zlib.error) as exc:
        sys.stderr.write(f"run_git: checkout: {exc}\n")
        return 1

    try:
        persist_head_symbolic_ref_atomic(repo_paths.head_file, branch_ref_name)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"run_git: checkout: unable to update HEAD: {exc}\n")
        return 1

    return 0
