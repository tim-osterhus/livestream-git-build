#!/usr/bin/env python3
"""Deterministic staged snapshot helpers persisted at `.git/index`."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Iterable

INDEX_FILE_NAME = "index"
INDEX_HEADER = "RUNGIT_INDEX_V1"
INDEX_ENTRY_PATTERN = re.compile(r"^(100644|100755) ([0-9a-f]{40})\t(.+)$")


@dataclass(frozen=True)
class IndexEntry:
    """Single staged path entry in deterministic index snapshot."""

    path: str
    mode: str
    object_id: str


def index_file_path(git_dir: Path) -> Path:
    """Return the deterministic index file path for a repository."""

    return git_dir / INDEX_FILE_NAME


def _validate_index_path(path: str) -> None:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or path.startswith("./"):
        raise ValueError(f"invalid staged path '{path}'")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"invalid staged path '{path}'")
    if parts[0] == ".git":
        raise ValueError("refusing to stage internal .git paths")


def _normalize_entries(entries: Iterable[IndexEntry]) -> list[IndexEntry]:
    by_path: dict[str, IndexEntry] = {}
    for entry in entries:
        _validate_index_path(entry.path)
        if entry.mode not in {"100644", "100755"}:
            raise ValueError(f"invalid staged mode '{entry.mode}' for path '{entry.path}'")
        if len(entry.object_id) != 40 or not all(c in "0123456789abcdef" for c in entry.object_id):
            raise ValueError(f"invalid staged oid '{entry.object_id}' for path '{entry.path}'")
        by_path[entry.path] = entry
    return sorted(by_path.values(), key=lambda item: item.path)


def load_index(index_path: Path) -> list[IndexEntry]:
    """Load index entries from disk. Missing index yields an empty snapshot."""

    if not index_path.exists():
        return []

    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("index file is not valid UTF-8") from exc

    if not lines:
        raise ValueError("index file is empty")
    if lines[0] != INDEX_HEADER:
        raise ValueError("unexpected index header")

    entries: list[IndexEntry] = []
    seen_paths: set[str] = set()
    for line in lines[1:]:
        if not line:
            continue
        match = INDEX_ENTRY_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError(f"malformed index entry: {line}")
        mode, object_id, path = match.groups()
        _validate_index_path(path)
        if path in seen_paths:
            raise ValueError(f"duplicate index path '{path}'")
        seen_paths.add(path)
        entries.append(IndexEntry(path=path, mode=mode, object_id=object_id))

    return sorted(entries, key=lambda item: item.path)


def upsert_entries(existing: Iterable[IndexEntry], updates: Iterable[IndexEntry]) -> list[IndexEntry]:
    """Merge staged entries by path and return deterministically sorted snapshot."""

    merged = list(existing) + list(updates)
    return _normalize_entries(merged)


def persist_index(index_path: Path, entries: Iterable[IndexEntry]) -> None:
    """Persist deterministic index content atomically."""

    normalized = _normalize_entries(entries)
    lines = [INDEX_HEADER]
    lines.extend(f"{entry.mode} {entry.object_id}\t{entry.path}" for entry in normalized)
    content = ("\n".join(lines) + "\n").encode("utf-8")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=index_path.parent,
            prefix=f".{index_path.name}.tmp-",
            delete=False,
        ) as tmp_file:
            tmp_file.write(content)
            temp_path = Path(tmp_file.name)
        os.replace(temp_path, index_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
