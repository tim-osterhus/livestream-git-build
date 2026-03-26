#!/usr/bin/env python3
"""Tree decoding helpers for deterministic merge evaluation inputs."""

from __future__ import annotations

from pathlib import Path

from objects import is_valid_object_id, read_object

_TREE_MODE = "40000"
_BLOB_MODES = frozenset({"100644", "100755"})


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


def load_tree_path_map(objects_dir: Path, tree_oid: str) -> dict[str, tuple[str, str]]:
    """Load tree entries recursively into a deterministic `path -> (mode, oid)` map."""

    if not is_valid_object_id(tree_oid):
        raise ValueError(f"invalid tree object id: {tree_oid}")

    entries: dict[str, tuple[str, str]] = {}
    _collect_tree_paths(objects_dir, tree_oid, "", entries, set())
    return {path: entries[path] for path in sorted(entries)}
