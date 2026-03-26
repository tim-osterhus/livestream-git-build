#!/usr/bin/env python3
"""Deterministic staged snapshot helpers persisted in a run_git sidecar file."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile
from typing import Iterable, Mapping

INDEX_FILE_NAME = "run_git.index"
LEGACY_INDEX_FILE_NAME = "index"
INDEX_HEADER = "RUNGIT_INDEX_V1"
INDEX_ENTRY_PATTERN = re.compile(r"^(100644|100755) ([0-9a-f]{40})\t(.+)$")
REGULAR_FILE_MODES = frozenset({"100644", "100755"})
HOST_INDEX_SIGNATURE = b"DIRC"
HOST_INDEX_VERSION = 2
HOST_INDEX_NAME_MASK = 0x0FFF


@dataclass(frozen=True)
class IndexEntry:
    """Single staged path entry in deterministic index snapshot."""

    path: str
    mode: str
    object_id: str


def index_file_path(git_dir: Path) -> Path:
    """Return run_git's sidecar index path for a repository."""

    return git_dir / INDEX_FILE_NAME


def is_regular_file_mode(mode: str) -> bool:
    """Return whether `mode` is a supported regular-file mode."""

    return mode in REGULAR_FILE_MODES


def require_regular_file_mode(mode: str, path: str) -> None:
    """Raise when a staged entry mode is outside regular-file policy."""

    if not is_regular_file_mode(mode):
        raise ValueError(f"invalid staged mode '{mode}' for path '{path}'")


def _validate_index_path(path: str) -> None:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or path.startswith("./"):
        raise ValueError(f"invalid staged path '{path}'")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"invalid staged path '{path}'")
    if parts[0] == ".git":
        raise ValueError("refusing to stage internal .git paths")


def normalize_index_path(path: str) -> str:
    """Normalize a staged path to canonical repo-relative POSIX form."""

    if not path:
        raise ValueError("invalid staged path ''")

    normalized = posixpath.normpath(path)
    if normalized in {"", "."} or normalized.startswith("/"):
        raise ValueError(f"invalid staged path '{path}'")
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"invalid staged path '{path}'")

    _validate_index_path(normalized)
    return normalized


def _normalize_entries(entries: Iterable[IndexEntry]) -> list[IndexEntry]:
    by_path: dict[str, IndexEntry] = {}
    for entry in entries:
        normalized_path = normalize_index_path(entry.path)
        require_regular_file_mode(entry.mode, entry.path)
        if len(entry.object_id) != 40 or not all(c in "0123456789abcdef" for c in entry.object_id):
            raise ValueError(f"invalid staged oid '{entry.object_id}' for path '{entry.path}'")
        by_path[normalized_path] = IndexEntry(
            path=normalized_path,
            mode=entry.mode,
            object_id=entry.object_id,
        )
    return sorted(by_path.values(), key=lambda item: item.path)


def _parse_index_lines(lines: list[str]) -> list[IndexEntry]:
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
        normalized_path = normalize_index_path(path)
        if normalized_path in seen_paths:
            raise ValueError(f"duplicate index path '{normalized_path}'")
        seen_paths.add(normalized_path)
        entries.append(IndexEntry(path=normalized_path, mode=mode, object_id=object_id))

    return sorted(entries, key=lambda item: item.path)


def _read_index_text(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("index file is not valid UTF-8") from exc


def _legacy_index_path(index_path: Path) -> Path:
    return index_path.parent / LEGACY_INDEX_FILE_NAME


def load_index(index_path: Path) -> list[IndexEntry]:
    """Load index entries from sidecar disk snapshot."""

    if index_path.exists():
        return _parse_index_lines(_read_index_text(index_path))

    legacy_path = _legacy_index_path(index_path)
    if not legacy_path.exists():
        return []

    legacy_prefix = f"{INDEX_HEADER}\n".encode("utf-8")
    if not legacy_path.read_bytes().startswith(legacy_prefix):
        return []
    return _parse_index_lines(_read_index_text(legacy_path))


def upsert_entries(existing: Iterable[IndexEntry], updates: Iterable[IndexEntry]) -> list[IndexEntry]:
    """Merge staged entries by path and return deterministically sorted snapshot."""

    merged = list(existing) + list(updates)
    return _normalize_entries(merged)


def _atomic_write_bytes(target_path: Path, content: bytes) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target_path.parent,
            prefix=f".{target_path.name}.tmp-",
            delete=False,
        ) as tmp_file:
            tmp_file.write(content)
            temp_path = Path(tmp_file.name)
        os.replace(temp_path, target_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def persist_index(index_path: Path, entries: Iterable[IndexEntry]) -> None:
    """Persist deterministic index content atomically."""

    normalized = _normalize_entries(entries)
    lines = [INDEX_HEADER]
    lines.extend(f"{entry.mode} {entry.object_id}\t{entry.path}" for entry in normalized)
    content = ("\n".join(lines) + "\n").encode("utf-8")

    _atomic_write_bytes(index_path, content)

    legacy_path = _legacy_index_path(index_path)
    if legacy_path.exists():
        legacy_prefix = f"{INDEX_HEADER}\n".encode("utf-8")
        if legacy_path.read_bytes().startswith(legacy_prefix):
            legacy_path.unlink()


def _index_entries_from_tree_entries(
    tree_entries: Mapping[str, tuple[str, str]],
) -> list[IndexEntry]:
    index_entries: list[IndexEntry] = []
    for path, value in tree_entries.items():
        if len(value) != 2:
            raise ValueError(f"invalid merged entry value for '{path}'")
        mode, object_id = value
        index_entries.append(IndexEntry(path=path, mode=mode, object_id=object_id))
    return _normalize_entries(index_entries)


def _serialize_host_index(entries: Iterable[IndexEntry]) -> bytes:
    normalized = _normalize_entries(entries)
    content = bytearray(
        struct.pack(
            ">4sLL",
            HOST_INDEX_SIGNATURE,
            HOST_INDEX_VERSION,
            len(normalized),
        )
    )

    for entry in normalized:
        path_bytes = entry.path.encode("utf-8")
        if b"\0" in path_bytes:
            raise ValueError(f"invalid staged path '{entry.path}'")

        flags = min(len(path_bytes), HOST_INDEX_NAME_MASK)
        object_id_bytes = bytes.fromhex(entry.object_id)
        record = bytearray(
            struct.pack(
                ">LLLLLLLLLL20sH",
                0,
                0,
                0,
                0,
                0,
                0,
                int(entry.mode, 8),
                0,
                0,
                0,
                object_id_bytes,
                flags,
            )
        )
        record.extend(path_bytes)
        record.append(0)
        record.extend(b"\0" * ((8 - (len(record) % 8)) % 8))
        content.extend(record)

    content.extend(hashlib.sha1(content).digest())
    return bytes(content)


def persist_merge_index_snapshot(
    git_dir: Path,
    merged_tree_entries: Mapping[str, tuple[str, str]],
) -> None:
    """Persist sidecar and host-readable index snapshots from merged tree entries."""

    entries = _index_entries_from_tree_entries(merged_tree_entries)
    sidecar_path = index_file_path(git_dir)
    persist_index(sidecar_path, entries)
    _atomic_write_bytes(_legacy_index_path(sidecar_path), _serialize_host_index(entries))
