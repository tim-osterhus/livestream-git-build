#!/usr/bin/env python3
"""`add` command implementation for deterministic staged snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
import sys
from typing import Sequence

from index import IndexEntry, index_file_path, load_index, persist_index, upsert_entries
from objects import compute_object_id, serialize_blob, write_loose_object
from repo import RepoPaths, discover_repo_paths

ADD_USAGE = "usage: run_git add <path>...\n"


@dataclass(frozen=True)
class _PreparedEntry:
    path: str
    mode: str
    object_id: str
    serialized: bytes


def _print_usage(stream: object) -> None:
    stream.write(ADD_USAGE)


def _resolve_input_path(path_arg: str, cwd: str | Path | None) -> Path:
    base_dir = Path(cwd).resolve() if cwd is not None else Path.cwd()
    return (base_dir / path_arg).resolve()


def _to_repo_relative(path: Path, repo_paths: RepoPaths, original_arg: str) -> str:
    try:
        relative = path.relative_to(repo_paths.worktree)
    except ValueError as exc:
        raise ValueError(f"path '{original_arg}' is outside the repository root") from exc

    relative_text = relative.as_posix()
    if relative_text in {"", "."}:
        raise ValueError(f"path '{original_arg}' does not reference a file")
    if relative.parts and relative.parts[0] == ".git":
        raise ValueError(f"path '{original_arg}' points inside .git")

    return relative_text


def _mode_for_stat(mode: int) -> str:
    return "100755" if mode & 0o111 else "100644"


def _prepare_entry(path_arg: str, cwd: str | Path | None, repo_paths: RepoPaths) -> _PreparedEntry:
    input_path = _resolve_input_path(path_arg, cwd)

    if not input_path.exists():
        raise ValueError(f"file not found: {path_arg}")

    file_stat = input_path.stat(follow_symlinks=False)
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"not a regular file: {path_arg}")

    staged_path = _to_repo_relative(input_path, repo_paths, path_arg)
    payload = input_path.read_bytes()
    serialized = serialize_blob(payload)
    object_id = compute_object_id(serialized)

    return _PreparedEntry(
        path=staged_path,
        mode=_mode_for_stat(file_stat.st_mode),
        object_id=object_id,
        serialized=serialized,
    )


def run_add(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Stage one or more regular files into deterministic `.git/index` snapshot."""

    if not args:
        sys.stderr.write("run_git: add requires at least one path.\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: add: not a git repository (missing .git).\n")
        return 1

    prepared_by_path: dict[str, _PreparedEntry] = {}
    for path_arg in args:
        try:
            prepared = _prepare_entry(path_arg, cwd, repo_paths)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"run_git: add: {exc}\n")
            return 1
        prepared_by_path[prepared.path] = prepared

    for path_key in sorted(prepared_by_path):
        prepared = prepared_by_path[path_key]
        write_loose_object(repo_paths.objects_dir, prepared.object_id, prepared.serialized)

    idx_path = index_file_path(repo_paths.git_dir)
    try:
        existing_entries = load_index(idx_path)
    except ValueError as exc:
        sys.stderr.write(f"run_git: add: invalid index: {exc}\n")
        return 1

    updates = [
        IndexEntry(path=item.path, mode=item.mode, object_id=item.object_id)
        for item in prepared_by_path.values()
    ]
    merged_entries = upsert_entries(existing_entries, updates)
    persist_index(idx_path, merged_entries)
    return 0
