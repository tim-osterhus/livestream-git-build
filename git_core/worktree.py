#!/usr/bin/env python3
"""Working-tree convergence helpers for merge materialization."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Mapping

from index import normalize_index_path, require_regular_file_mode
from objects import read_object
from repo import RepoPaths


def _path_from_index(worktree: Path, index_path: str) -> Path:
    return worktree.joinpath(*index_path.split("/"))


def materialize_merge_worktree(
    paths: RepoPaths,
    merged_tree_entries: Mapping[str, tuple[str, str]],
) -> None:
    """Write merged-tree blobs into the working tree using deterministic path order."""

    for path in sorted(merged_tree_entries):
        value = merged_tree_entries[path]
        if len(value) != 2:
            raise ValueError(f"invalid merged entry value for '{path}'")
        mode, object_id = value
        normalized = normalize_index_path(path)
        if normalized != path:
            raise ValueError(f"merged path is not canonical: '{path}'")
        require_regular_file_mode(mode, path)

        object_type, body = read_object(paths.objects_dir, object_id)
        if object_type != "blob":
            raise ValueError(f"object '{object_id}' is not a blob")

        full_path = _path_from_index(paths.worktree, path)
        if full_path.exists() and full_path.is_dir():
            shutil.rmtree(full_path)

        parent = full_path.parent
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"path conflict while creating '{path}'")
        parent.mkdir(parents=True, exist_ok=True)

        full_path.write_bytes(body)
        full_path.chmod(0o755 if mode == "100755" else 0o644)
