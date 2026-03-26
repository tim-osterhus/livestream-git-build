#!/usr/bin/env python3
"""Git loose-object helpers for canonical blob encoding and storage."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import Iterable
import tempfile
import zlib

OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class CommitMetadata:
    """Parsed commit metadata required by merge/tree readers."""

    tree_oid: str
    parent_oids: tuple[str, ...]


def serialize_blob(payload: bytes) -> bytes:
    """Encode payload as canonical Git blob bytes."""

    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    return header + payload


def serialize_tree(entries: Iterable[tuple[str, str, str]]) -> bytes:
    """Encode canonical Git tree bytes from `(mode, name, oid)` entries."""

    chunks: list[bytes] = []
    for mode, name, object_id in entries:
        if not name or "/" in name or "\0" in name:
            raise ValueError(f"invalid tree entry name '{name}'")
        if not is_valid_object_id(object_id):
            raise ValueError(f"invalid tree entry object id: {object_id}")
        try:
            mode_bytes = mode.encode("ascii")
            name_bytes = name.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("tree entry encoding is invalid") from exc

        chunks.append(mode_bytes + b" " + name_bytes + b"\0" + bytes.fromhex(object_id))

    body = b"".join(chunks)
    header = b"tree " + str(len(body)).encode("ascii") + b"\0"
    return header + body


def compute_object_id(serialized: bytes) -> str:
    """Return the lowercase hex SHA1 object id for serialized object bytes."""

    return hashlib.sha1(serialized).hexdigest()


def loose_object_path(objects_dir: Path, object_id: str) -> Path:
    """Resolve a loose-object path from an object id."""

    if not is_valid_object_id(object_id):
        raise ValueError(f"invalid object id: {object_id}")
    return objects_dir / object_id[:2] / object_id[2:]


def write_loose_object(objects_dir: Path, object_id: str, serialized: bytes) -> Path:
    """Compress and atomically store a loose object if it is not present."""

    target = loose_object_path(objects_dir, object_id)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        return target

    compressed = zlib.compress(serialized)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.tmp-",
            delete=False,
        ) as tmp_file:
            tmp_file.write(compressed)
            temp_path = Path(tmp_file.name)
        if target.exists():
            return target
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    return target


def serialize_commit(
    tree_oid: str,
    parent_oid: str | None,
    author: tuple[str, str, str],
    committer: tuple[str, str, str],
    message: str,
) -> bytes:
    """Encode a canonical Git commit object payload (zero/one parent form)."""

    parent_oids: tuple[str, ...]
    if parent_oid is None:
        parent_oids = ()
    else:
        parent_oids = (parent_oid,)

    return serialize_commit_with_parents(
        tree_oid=tree_oid,
        parent_oids=parent_oids,
        author=author,
        committer=committer,
        message=message,
    )


def serialize_commit_with_parents(
    tree_oid: str,
    parent_oids: Iterable[str],
    author: tuple[str, str, str],
    committer: tuple[str, str, str],
    message: str,
) -> bytes:
    """Encode a canonical Git commit object payload with ordered parent headers."""

    if not is_valid_object_id(tree_oid):
        raise ValueError(f"invalid tree object id: {tree_oid}")

    ordered_parents = tuple(parent_oids)
    for parent_oid in ordered_parents:
        if not is_valid_object_id(parent_oid):
            raise ValueError(f"invalid parent object id: {parent_oid}")

    author_name, author_email, author_date = author
    committer_name, committer_email, committer_date = committer

    lines = [f"tree {tree_oid}"]
    for parent_oid in ordered_parents:
        lines.append(f"parent {parent_oid}")
    lines.append(f"author {author_name} <{author_email}> {author_date}")
    lines.append(f"committer {committer_name} <{committer_email}> {committer_date}")
    lines.append("")
    lines.append(message)

    body = ("\n".join(lines) + "\n").encode("utf-8")
    header = b"commit " + str(len(body)).encode("ascii") + b"\0"
    return header + body


def is_valid_object_id(object_id: str) -> bool:
    """Return whether object_id is a lowercase 40-hex oid."""

    return bool(OBJECT_ID_PATTERN.fullmatch(object_id))


def read_loose_object(objects_dir: Path, object_id: str) -> bytes:
    """Read and decompress a loose object payload."""

    object_path = loose_object_path(objects_dir, object_id)
    compressed = object_path.read_bytes()
    return zlib.decompress(compressed)


def decode_object(serialized: bytes) -> tuple[str, bytes]:
    """Parse canonical object bytes into (type, body)."""

    if b"\0" not in serialized:
        raise ValueError("missing object header terminator")

    header, body = serialized.split(b"\0", 1)
    kind_bytes, separator, size_bytes = header.partition(b" ")
    if not separator or not kind_bytes or not size_bytes:
        raise ValueError("invalid object header")

    try:
        kind = kind_bytes.decode("ascii")
        declared_size = int(size_bytes.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid object header encoding") from exc

    if declared_size != len(body):
        raise ValueError("object size header does not match payload length")

    return kind, body


def read_object(objects_dir: Path, object_id: str) -> tuple[str, bytes]:
    """Read and decode a loose object by oid."""

    serialized = read_loose_object(objects_dir, object_id)
    return decode_object(serialized)


def parse_commit_metadata(body: bytes) -> CommitMetadata:
    """Parse commit headers into validated tree/parent object ids."""

    headers, separator, _ = body.partition(b"\n\n")
    if not separator:
        raise ValueError("commit missing header/message separator")

    tree_oid: str | None = None
    parent_oids: list[str] = []
    for line in headers.split(b"\n"):
        if line.startswith(b"tree "):
            if tree_oid is not None:
                raise ValueError("commit has multiple tree headers")
            tree_value = line[len(b"tree ") :].strip()
            try:
                candidate = tree_value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError("commit tree header is not valid ASCII") from exc
            if not is_valid_object_id(candidate):
                raise ValueError("commit tree header has invalid object id")
            tree_oid = candidate
            continue

        if line.startswith(b"parent "):
            parent_value = line[len(b"parent ") :].strip()
            try:
                parent_oid = parent_value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError("commit parent header is not valid ASCII") from exc
            if not is_valid_object_id(parent_oid):
                raise ValueError("commit parent header has invalid object id")
            parent_oids.append(parent_oid)

    if tree_oid is None:
        raise ValueError("commit is missing tree header")

    return CommitMetadata(tree_oid=tree_oid, parent_oids=tuple(parent_oids))


def read_commit_metadata(objects_dir: Path, object_id: str) -> CommitMetadata:
    """Read a commit object and return validated merge-relevant metadata."""

    if not is_valid_object_id(object_id):
        raise ValueError(f"invalid object id: {object_id}")

    kind, body = read_object(objects_dir, object_id)
    if kind != "commit":
        raise ValueError(f"object '{object_id}' is not a commit")
    return parse_commit_metadata(body)
