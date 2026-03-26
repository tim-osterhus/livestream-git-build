#!/usr/bin/env python3
"""Tree object construction from deterministic staged index entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable

from index import IndexEntry
from objects import compute_object_id, write_loose_object


@dataclass
class _TreeNode:
    blobs: dict[str, tuple[str, str]] = field(default_factory=dict)
    children: dict[str, "_TreeNode"] = field(default_factory=dict)


def _serialize_tree_body(entries: Iterable[tuple[str, str, str]]) -> bytes:
    chunks: list[bytes] = []
    for mode, name, object_id in entries:
        chunks.append(f"{mode} {name}".encode("utf-8") + b"\0" + bytes.fromhex(object_id))
    return b"".join(chunks)


def _serialize_tree_object(tree_body: bytes) -> bytes:
    header = b"tree " + str(len(tree_body)).encode("ascii") + b"\0"
    return header + tree_body


def _entry_sort_key(mode: str, name: str) -> bytes:
    # Match Git tree ordering semantics by sorting directories as if suffixed with '/'.
    suffix = "/" if mode == "40000" else ""
    return f"{name}{suffix}".encode("utf-8")


def _insert_entry(root: _TreeNode, entry: IndexEntry) -> None:
    parts = PurePosixPath(entry.path).parts
    if not parts:
        raise ValueError(f"invalid staged path '{entry.path}'")

    node = root
    for segment in parts[:-1]:
        if segment in node.blobs:
            raise ValueError(f"staged path conflict at '{entry.path}'")
        node = node.children.setdefault(segment, _TreeNode())

    leaf = parts[-1]
    if leaf in node.children:
        raise ValueError(f"staged path conflict at '{entry.path}'")
    node.blobs[leaf] = (entry.mode, entry.object_id)


def _write_tree_node(objects_dir, node: _TreeNode) -> str:
    encoded_entries: list[tuple[str, str, str]] = []

    for name, child in node.children.items():
        child_oid = _write_tree_node(objects_dir, child)
        encoded_entries.append(("40000", name, child_oid))

    for name, (mode, object_id) in node.blobs.items():
        encoded_entries.append((mode, name, object_id))

    encoded_entries.sort(key=lambda item: _entry_sort_key(item[0], item[1]))

    tree_body = _serialize_tree_body(encoded_entries)
    serialized = _serialize_tree_object(tree_body)
    object_id = compute_object_id(serialized)
    write_loose_object(objects_dir, object_id, serialized)
    return object_id


def write_tree_from_index(objects_dir, entries: Iterable[IndexEntry]) -> str:
    """Write tree objects for staged entries and return the root tree oid."""

    root = _TreeNode()
    for entry in entries:
        _insert_entry(root, entry)

    return _write_tree_node(objects_dir, root)
