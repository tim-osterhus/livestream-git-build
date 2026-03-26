#!/usr/bin/env python3
"""`tag` command implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

from refs import persist_ref_atomic, read_head_commit_oid, read_tag_tip_by_name
from repo import discover_repo_paths

TAG_USAGE = "usage: run_git tag <name>\n"


def _print_usage(stream: object) -> None:
    stream.write(TAG_USAGE)


def _parse_tag_args(args: Sequence[str]) -> str:
    if len(args) != 1:
        raise ValueError("tag requires exactly '<name>'")
    if not args[0]:
        raise ValueError("tag name must not be empty")
    return args[0]


def run_tag(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Create `refs/tags/<name>` pointing at the current HEAD commit."""

    try:
        tag_name = _parse_tag_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: tag: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: tag: not a git repository (missing .git).\n")
        return 1

    try:
        read_tag_tip_by_name(repo_paths, tag_name)
        head_oid = read_head_commit_oid(repo_paths.head_file, repo_paths.git_dir)
    except ValueError as exc:
        sys.stderr.write(f"run_git: tag: {exc}\n")
        return 1

    if head_oid is None:
        sys.stderr.write("run_git: tag: HEAD does not point to a commit.\n")
        return 1

    try:
        persist_ref_atomic(repo_paths.tag_ref_path(tag_name), head_oid)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"run_git: tag: unable to update tag ref: {exc}\n")
        return 1

    return 0
