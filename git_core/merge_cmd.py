#!/usr/bin/env python3
"""`merge` command implementation (target resolution and validation slice)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence
import zlib

from objects import read_object
from refs import resolve_merge_target_oid
from repo import RepoPaths, discover_repo_paths

MERGE_USAGE = "usage: run_git merge <branch>\n"


def _print_usage(stream: object) -> None:
    stream.write(MERGE_USAGE)


def _parse_merge_args(args: Sequence[str]) -> str:
    if len(args) != 1:
        raise ValueError("merge requires exactly '<branch>'")
    if not args[0]:
        raise ValueError("merge target branch must not be empty")
    return args[0]


def _validate_commit_target(paths: RepoPaths, target_oid: str) -> None:
    try:
        object_type, _ = read_object(paths.objects_dir, target_oid)
    except FileNotFoundError:
        raise ValueError(f"merge target object not found: {target_oid}") from None
    except (ValueError, OSError, RuntimeError, EOFError, zlib.error):
        raise ValueError(f"unable to decode merge target object: {target_oid}") from None

    if object_type != "commit":
        raise ValueError(f"merge target '{target_oid}' is not a commit object")


def run_merge(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Resolve and validate merge target; merge semantics remain scaffolded."""

    try:
        branch_name = _parse_merge_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: merge: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: merge: not a git repository (missing .git).\n")
        return 1

    try:
        target_oid = resolve_merge_target_oid(repo_paths, branch_name)
        _validate_commit_target(repo_paths, target_oid)
    except ValueError as exc:
        sys.stderr.write(f"run_git: merge: {exc}\n")
        return 1

    sys.stderr.write(
        "run_git: subcommand 'merge' handler is scaffolded but not implemented yet.\n"
    )
    return 3
