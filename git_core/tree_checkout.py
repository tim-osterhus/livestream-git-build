#!/usr/bin/env python3
"""Working-tree materialization helpers for `checkout`."""

from __future__ import annotations

from pathlib import Path
import shutil

from index import IndexEntry, index_file_path, normalize_index_path, persist_index
from objects import is_valid_object_id, read_object
from repo import RepoPaths

_TREE_MODE = "40000"
_REGULAR_FILE_MODES = frozenset({"100644", "100755"})


def _parse_commit_tree_oid(commit_body: bytes) -> str:
    header, _, _ = commit_body.partition(b"\n\n")
    for line in header.split(b"\n"):
        if not line.startswith(b"tree "):
            continue
        try:
            tree_oid = line[len("tree ") :].decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("commit tree header is not valid ASCII") from exc
        if not is_valid_object_id(tree_oid):
            raise ValueError("commit tree header has invalid object id")
        return tree_oid
    raise ValueError("commit is missing tree header")


def _parse_tree_entries(tree_body: bytes) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    cursor = 0

    while cursor < len(tree_body):
        mode_end = tree_body.find(b" ", cursor)
        if mode_end == -1:
            raise ValueError("malformed tree entry mode")

        name_end = tree_body.find(b"\0", mode_end + 1)
        if name_end == -1:
            raise ValueError("malformed tree entry name")

        object_start = name_end + 1
        object_end = object_start + 20
        if object_end > len(tree_body):
            raise ValueError("malformed tree entry object id")

        mode_bytes = tree_body[cursor:mode_end]
        name_bytes = tree_body[mode_end + 1 : name_end]
        object_id = tree_body[object_start:object_end].hex()

        try:
            mode = mode_bytes.decode("ascii")
            name = name_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("tree entry encoding is invalid") from exc

        if not name or "/" in name or name in {".", ".."}:
            raise ValueError("tree entry name is invalid")

        entries.append((mode, name, object_id))
        cursor = object_end

    return entries


def _collect_commit_entries(
    objects_dir: Path,
    tree_oid: str,
    prefix: str,
    out_entries: dict[str, tuple[str, str]],
) -> None:
    object_type, body = read_object(objects_dir, tree_oid)
    if object_type != "tree":
        raise ValueError(f"object '{tree_oid}' is not a tree")

    for mode, name, object_id in _parse_tree_entries(body):
        if mode == _TREE_MODE:
            _collect_commit_entries(objects_dir, object_id, f"{prefix}{name}/", out_entries)
            continue

        if mode not in _REGULAR_FILE_MODES:
            raise ValueError(f"unsupported tree entry mode '{mode}'")
        if not is_valid_object_id(object_id):
            raise ValueError("tree entry has invalid object id")

        path = normalize_index_path(f"{prefix}{name}")
        if path in out_entries:
            raise ValueError(f"duplicate tree path '{path}'")
        out_entries[path] = (mode, object_id)


def _read_commit_entries(objects_dir: Path, commit_oid: str) -> dict[str, tuple[str, str]]:
    if not is_valid_object_id(commit_oid):
        raise ValueError(f"invalid commit object id: {commit_oid}")

    object_type, body = read_object(objects_dir, commit_oid)
    if object_type != "commit":
        raise ValueError(f"object '{commit_oid}' is not a commit")

    tree_oid = _parse_commit_tree_oid(body)
    entries: dict[str, tuple[str, str]] = {}
    _collect_commit_entries(objects_dir, tree_oid, "", entries)
    return entries


def _path_from_index(worktree: Path, index_path: str) -> Path:
    return worktree.joinpath(*index_path.split("/"))


def _remove_stale_paths(worktree: Path, stale_paths: set[str]) -> None:
    for path in sorted(stale_paths):
        full_path = _path_from_index(worktree, path)
        if full_path.is_file() or full_path.is_symlink():
            full_path.unlink()
        elif full_path.exists():
            raise ValueError(f"unable to remove non-file path '{path}'")

    for path in sorted(stale_paths, key=lambda value: value.count("/"), reverse=True):
        parent = _path_from_index(worktree, path).parent
        while parent != worktree and parent != worktree / ".git":
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def _write_target_paths(worktree: Path, objects_dir: Path, entries: dict[str, tuple[str, str]]) -> None:
    for path in sorted(entries):
        mode, object_id = entries[path]
        object_type, body = read_object(objects_dir, object_id)
        if object_type != "blob":
            raise ValueError(f"object '{object_id}' is not a blob")

        full_path = _path_from_index(worktree, path)
        if full_path.exists() and full_path.is_dir():
            shutil.rmtree(full_path)

        parent = full_path.parent
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"path conflict while creating '{path}'")
        parent.mkdir(parents=True, exist_ok=True)

        full_path.write_bytes(body)
        full_path.chmod(0o755 if mode == "100755" else 0o644)


def _persist_checkout_index(paths: RepoPaths, entries: dict[str, tuple[str, str]]) -> None:
    index_entries = [
        IndexEntry(path=path, mode=mode, object_id=object_id)
        for path, (mode, object_id) in sorted(entries.items())
    ]
    persist_index(index_file_path(paths.git_dir), index_entries)


def materialize_commit_checkout(
    paths: RepoPaths,
    target_commit_oid: str,
    current_commit_oid: str | None,
) -> None:
    """Materialize target commit tree in worktree and sync deterministic index."""

    target_entries = _read_commit_entries(paths.objects_dir, target_commit_oid)
    current_entries = (
        _read_commit_entries(paths.objects_dir, current_commit_oid)
        if current_commit_oid is not None
        else {}
    )

    stale_paths = set(current_entries).difference(target_entries)
    _remove_stale_paths(paths.worktree, stale_paths)
    _write_target_paths(paths.worktree, paths.objects_dir, target_entries)
    _persist_checkout_index(paths, target_entries)
