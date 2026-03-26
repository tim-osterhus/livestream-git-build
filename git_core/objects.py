#!/usr/bin/env python3
"""Git loose-object helpers for canonical blob encoding and storage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import zlib


def serialize_blob(payload: bytes) -> bytes:
    """Encode payload as canonical Git blob bytes."""

    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    return header + payload


def compute_object_id(serialized: bytes) -> str:
    """Return the lowercase hex SHA1 object id for serialized object bytes."""

    return hashlib.sha1(serialized).hexdigest()


def loose_object_path(objects_dir: Path, object_id: str) -> Path:
    """Resolve a loose-object path from an object id."""

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
