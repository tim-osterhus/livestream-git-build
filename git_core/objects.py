#!/usr/bin/env python3
"""Git loose-object helpers for canonical blob encoding and storage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
import zlib

OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def serialize_blob(payload: bytes) -> bytes:
    """Encode payload as canonical Git blob bytes."""

    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    return header + payload


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
