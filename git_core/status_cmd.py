#!/usr/bin/env python3
"""`status` command implementation."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from typing import Sequence
import zlib

from index import index_file_path, load_index, normalize_index_path
from objects import read_object
from repo import RepoPaths, discover_repo_paths

STATUS_USAGE = "usage: run_git status\n"


def _print_usage(stream: object) -> None:
    stream.write(STATUS_USAGE)


def _parse_status_args(args: Sequence[str]) -> None:
    if args:
        raise ValueError("status does not accept positional arguments")


def _path_from_index(worktree: Path, index_path: str) -> Path:
    return worktree.joinpath(*index_path.split("/"))


def _scan_worktree_files(paths: RepoPaths) -> list[str]:
    file_paths: set[str] = set()
    for root, dirs, files in os.walk(paths.worktree, topdown=True):
        dirs[:] = sorted(directory for directory in dirs if directory != ".git")
        for file_name in sorted(files):
            full_path = Path(root) / file_name
            if not full_path.is_file():
                continue
            try:
                relative_path = full_path.relative_to(paths.worktree).as_posix()
                file_paths.add(normalize_index_path(relative_path))
            except ValueError:
                continue
    return sorted(file_paths)


def _detect_untracked_paths(tracked_paths: set[str], worktree_paths: list[str]) -> list[str]:
    return [path for path in worktree_paths if path not in tracked_paths]


def _detect_modified_paths(paths: RepoPaths, tracked_entries) -> list[str]:
    modified: list[str] = []

    for entry in sorted(tracked_entries, key=lambda item: item.path):
        worktree_path = _path_from_index(paths.worktree, entry.path)
        if not worktree_path.exists() or not worktree_path.is_file():
            modified.append(entry.path)
            continue

        object_type, tracked_body = read_object(paths.objects_dir, entry.object_id)
        if object_type != "blob":
            raise ValueError(f"tracked object '{entry.object_id}' is not a blob")

        if worktree_path.read_bytes() != tracked_body:
            modified.append(entry.path)

    return modified


def _render_status(modified_paths: list[str], untracked_paths: list[str]) -> str:
    lines: list[str] = []

    if modified_paths:
        lines.append("modified:")
        lines.extend(f"  {path}" for path in modified_paths)

    if untracked_paths:
        lines.append("untracked:")
        lines.extend(f"  {path}" for path in untracked_paths)

    if not lines:
        lines.append("clean")

    return "\n".join(lines) + "\n"


def run_status(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Report deterministic modified/untracked path status."""

    try:
        _parse_status_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: status: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    paths = discover_repo_paths(cwd)
    if not paths.git_dir.is_dir():
        sys.stderr.write("run_git: status: not a git repository (missing .git).\n")
        return 1

    try:
        tracked_entries = load_index(index_file_path(paths.git_dir))
        tracked_paths = {entry.path for entry in tracked_entries}
        worktree_paths = _scan_worktree_files(paths)
        untracked_paths = _detect_untracked_paths(tracked_paths, worktree_paths)
        modified_paths = _detect_modified_paths(paths, tracked_entries)
    except (OSError, RuntimeError, EOFError, ValueError, zlib.error) as exc:
        sys.stderr.write(f"run_git: status: {exc}\n")
        return 1

    sys.stdout.write(_render_status(modified_paths, untracked_paths))
    return 0
