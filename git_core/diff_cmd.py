#!/usr/bin/env python3
"""`diff` command implementation."""

from __future__ import annotations

import difflib
from pathlib import Path
import sys
from typing import Sequence
import zlib

from index import index_file_path, load_index
from objects import read_object
from repo import discover_repo_paths

DIFF_USAGE = "usage: run_git diff\n"


def _print_usage(stream: object) -> None:
    stream.write(DIFF_USAGE)


def _parse_diff_args(args: Sequence[str]) -> None:
    if args:
        raise ValueError("diff does not accept positional arguments")


def _path_from_index(worktree: Path, index_path: str) -> Path:
    return worktree.joinpath(*index_path.split("/"))


def _decode_for_diff(payload: bytes) -> list[str]:
    return payload.decode("utf-8", errors="replace").splitlines()


def _build_file_diff(path: str, tracked_body: bytes, worktree_body: bytes) -> list[str]:
    unified = list(
        difflib.unified_diff(
            _decode_for_diff(tracked_body),
            _decode_for_diff(worktree_body),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )

    if not unified:
        return []
    return [f"diff --git a/{path} b/{path}"] + unified


def _collect_modified_file_diffs(paths, tracked_entries) -> list[str]:
    rendered: list[str] = []

    for entry in sorted(tracked_entries, key=lambda item: item.path):
        worktree_path = _path_from_index(paths.worktree, entry.path)
        if worktree_path.exists() and worktree_path.is_file():
            worktree_body = worktree_path.read_bytes()
        else:
            worktree_body = b""

        object_type, tracked_body = read_object(paths.objects_dir, entry.object_id)
        if object_type != "blob":
            raise ValueError(f"tracked object '{entry.object_id}' is not a blob")

        if tracked_body == worktree_body:
            continue

        rendered.extend(_build_file_diff(entry.path, tracked_body, worktree_body))

    return rendered


def run_diff(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Render deterministic tracked-file content diffs."""

    try:
        _parse_diff_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: diff: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: diff: not a git repository (missing .git).\n")
        return 1

    try:
        tracked_entries = load_index(index_file_path(repo_paths.git_dir))
        lines = _collect_modified_file_diffs(repo_paths, tracked_entries)
    except (OSError, RuntimeError, EOFError, ValueError, zlib.error) as exc:
        sys.stderr.write(f"run_git: diff: {exc}\n")
        return 1

    if lines:
        sys.stdout.write("\n".join(lines))
        sys.stdout.write("\n")
    return 0
