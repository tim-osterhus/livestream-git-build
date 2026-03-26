#!/usr/bin/env python3
"""Tree decoding helpers for deterministic merge evaluation inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Mapping

from objects import compute_object_id, is_valid_object_id, read_object, serialize_tree, write_loose_object

_TREE_MODE = "40000"
_BLOB_MODES = frozenset({"100644", "100755"})
TreePathMap = dict[str, tuple[str, str]]


@dataclass(frozen=True)
class MergePathUnionResult:
    """Deterministic path-union output for non-conflicting merge slices."""

    merged_entries: TreePathMap
    conflict_paths: tuple[str, ...]


@dataclass
class _TreeNode:
    blobs: dict[str, tuple[str, str]]
    children: dict[str, "_TreeNode"]


def _new_tree_node() -> _TreeNode:
    return _TreeNode(blobs={}, children={})


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

        if not name or "/" in name:
            raise ValueError("tree entry name is invalid")

        entries.append((mode, name, object_id))
        cursor = object_end

    return entries


def _collect_tree_paths(
    objects_dir: Path,
    tree_oid: str,
    prefix: str,
    out_entries: dict[str, tuple[str, str]],
    seen_tree_oids: set[str],
) -> None:
    if tree_oid in seen_tree_oids:
        raise ValueError("detected tree cycle")
    seen_tree_oids.add(tree_oid)

    kind, body = read_object(objects_dir, tree_oid)
    if kind != "tree":
        raise ValueError(f"object '{tree_oid}' is not a tree")

    for mode, name, object_id in _parse_tree_entries(body):
        path = f"{prefix}{name}"
        if mode == _TREE_MODE:
            if not is_valid_object_id(object_id):
                raise ValueError("tree entry has invalid object id")
            _collect_tree_paths(
                objects_dir,
                object_id,
                f"{path}/",
                out_entries,
                seen_tree_oids,
            )
            continue

        if mode not in _BLOB_MODES:
            raise ValueError(f"unsupported tree entry mode '{mode}'")
        if not is_valid_object_id(object_id):
            raise ValueError("tree entry has invalid object id")
        if path in out_entries:
            raise ValueError(f"duplicate tree path '{path}'")
        out_entries[path] = (mode, object_id)

    seen_tree_oids.remove(tree_oid)


def load_tree_path_map(objects_dir: Path, tree_oid: str) -> TreePathMap:
    """Load tree entries recursively into a deterministic `path -> (mode, oid)` map."""

    if not is_valid_object_id(tree_oid):
        raise ValueError(f"invalid tree object id: {tree_oid}")

    entries: dict[str, tuple[str, str]] = {}
    _collect_tree_paths(objects_dir, tree_oid, "", entries, set())
    return {path: entries[path] for path in sorted(entries)}


def _entry_sort_key(mode: str, name: str) -> bytes:
    suffix = "/" if mode == _TREE_MODE else ""
    return f"{name}{suffix}".encode("utf-8")


def _insert_path_entry(root: _TreeNode, path: str, mode: str, object_id: str) -> None:
    if mode not in _BLOB_MODES:
        raise ValueError(f"unsupported merged entry mode '{mode}'")
    if not is_valid_object_id(object_id):
        raise ValueError(f"merged entry has invalid object id for '{path}'")

    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"invalid merged path '{path}'")

    node = root
    for segment in parts[:-1]:
        if segment in node.blobs:
            raise ValueError(f"merged path conflict at '{path}'")
        node = node.children.setdefault(segment, _new_tree_node())

    leaf = parts[-1]
    if leaf in node.children or leaf in node.blobs:
        raise ValueError(f"merged path conflict at '{path}'")
    node.blobs[leaf] = (mode, object_id)


def _write_tree_node(objects_dir: Path, node: _TreeNode) -> str:
    tree_entries: list[tuple[str, str, str]] = []

    for name, child in node.children.items():
        child_oid = _write_tree_node(objects_dir, child)
        tree_entries.append((_TREE_MODE, name, child_oid))

    for name, (mode, object_id) in node.blobs.items():
        tree_entries.append((mode, name, object_id))

    tree_entries.sort(key=lambda item: _entry_sort_key(item[0], item[1]))
    serialized = serialize_tree(tree_entries)
    tree_oid = compute_object_id(serialized)
    write_loose_object(objects_dir, tree_oid, serialized)
    return tree_oid


def write_tree_from_path_map(
    objects_dir: Path,
    entries: Mapping[str, tuple[str, str]],
) -> str:
    """Write deterministic tree objects from `path -> (mode, oid)` entries."""

    root = _new_tree_node()
    for path in sorted(entries):
        mode, object_id = entries[path]
        _insert_path_entry(root, path, mode, object_id)

    return _write_tree_node(objects_dir, root)


def merge_non_conflicting_path_union(
    current_entries: Mapping[str, tuple[str, str]],
    target_entries: Mapping[str, tuple[str, str]],
) -> MergePathUnionResult:
    """Merge disjoint paths and flag same-path entry mismatches as conflicts."""

    merged_entries: dict[str, tuple[str, str]] = {}
    conflict_paths: list[str] = []

    for path in sorted(set(current_entries).union(target_entries)):
        current_entry = current_entries.get(path)
        target_entry = target_entries.get(path)

        if current_entry is None:
            if target_entry is None:
                continue
            merged_entries[path] = target_entry
            continue
        if target_entry is None:
            merged_entries[path] = current_entry
            continue
        if current_entry == target_entry:
            merged_entries[path] = current_entry
            continue

        conflict_paths.append(path)

    return MergePathUnionResult(
        merged_entries={path: merged_entries[path] for path in sorted(merged_entries)},
        conflict_paths=tuple(conflict_paths),
    )
