#!/usr/bin/env python3
"""`merge` command implementation (target resolution and validation slice)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Sequence
import zlib

from objects import CommitMetadata, read_commit_metadata, read_object
from refs import read_head_commit_oid, resolve_merge_target_oid
from repo import RepoPaths, discover_repo_paths
from trees import load_tree_path_map, merge_non_conflicting_path_union

MERGE_USAGE = "usage: run_git merge <branch>\n"


@dataclass(frozen=True)
class MergeParentInputs:
    """Loaded merge-parent structures used by later merge phases."""

    current_commit_oid: str
    target_commit_oid: str
    current_commit: CommitMetadata
    target_commit: CommitMetadata
    current_tree_entries: dict[str, tuple[str, str]]
    target_tree_entries: dict[str, tuple[str, str]]
    merged_tree_entries: dict[str, tuple[str, str]]
    conflict_paths: tuple[str, ...]


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


def _read_commit_for_merge(paths: RepoPaths, commit_oid: str, label: str) -> CommitMetadata:
    try:
        return read_commit_metadata(paths.objects_dir, commit_oid)
    except FileNotFoundError:
        raise ValueError(f"{label} commit object not found: {commit_oid}") from None
    except (ValueError, OSError, RuntimeError, EOFError, zlib.error):
        raise ValueError(f"unable to decode {label} commit object: {commit_oid}") from None


def _read_tree_for_merge(
    paths: RepoPaths,
    tree_oid: str,
    label: str,
) -> dict[str, tuple[str, str]]:
    try:
        return load_tree_path_map(paths.objects_dir, tree_oid)
    except FileNotFoundError:
        raise ValueError(f"{label} tree object not found: {tree_oid}") from None
    except (ValueError, OSError, RuntimeError, EOFError, zlib.error):
        raise ValueError(f"unable to decode {label} tree object: {tree_oid}") from None


def _load_merge_parent_inputs(paths: RepoPaths, target_oid: str) -> MergeParentInputs:
    head_oid = read_head_commit_oid(paths.head_file, paths.git_dir)
    if head_oid is None:
        raise ValueError("HEAD does not point to a commit.")

    current_commit = _read_commit_for_merge(paths, head_oid, "current HEAD")
    target_commit = _read_commit_for_merge(paths, target_oid, "merge target")

    current_tree_entries = _read_tree_for_merge(
        paths, current_commit.tree_oid, "current HEAD commit"
    )
    target_tree_entries = _read_tree_for_merge(
        paths, target_commit.tree_oid, "merge target commit"
    )
    union_result = merge_non_conflicting_path_union(
        current_tree_entries,
        target_tree_entries,
    )

    return MergeParentInputs(
        current_commit_oid=head_oid,
        target_commit_oid=target_oid,
        current_commit=current_commit,
        target_commit=target_commit,
        current_tree_entries=current_tree_entries,
        target_tree_entries=target_tree_entries,
        merged_tree_entries=union_result.merged_entries,
        conflict_paths=union_result.conflict_paths,
    )


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
        _merge_inputs = _load_merge_parent_inputs(repo_paths, target_oid)
    except ValueError as exc:
        sys.stderr.write(f"run_git: merge: {exc}\n")
        return 1

    sys.stderr.write(
        "run_git: subcommand 'merge' handler is scaffolded but not implemented yet.\n"
    )
    return 3
