#!/usr/bin/env python3
"""Reference bootstrap helpers for repository initialization."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from objects import is_valid_object_id
from repo import RepoPaths

DEFAULT_BRANCH = "main"
DEFAULT_HEAD_REF = f"refs/heads/{DEFAULT_BRANCH}"
DEFAULT_HEAD_CONTENT = f"ref: {DEFAULT_HEAD_REF}\n"
_HEAD_REF_PREFIX = "ref: "
_LOCAL_HEAD_PREFIX = "refs/heads/"


def _is_local_branch_symbolic_ref(content: str) -> bool:
    return content.startswith("ref: refs/heads/")


def ensure_init_ref_layout(paths: RepoPaths) -> None:
    """Create required ref namespaces and initialize HEAD deterministically."""

    paths.refs_dir.mkdir(parents=True, exist_ok=True)
    paths.heads_dir.mkdir(parents=True, exist_ok=True)
    paths.tags_dir.mkdir(parents=True, exist_ok=True)

    if not paths.head_file.exists():
        paths.head_file.write_text(DEFAULT_HEAD_CONTENT, encoding="utf-8")
        return

    head_content = paths.head_file.read_text(encoding="utf-8")
    if _is_local_branch_symbolic_ref(head_content):
        return


def read_current_head_ref(head_path: Path) -> str:
    """Resolve the current symbolic branch ref from HEAD."""

    try:
        content = head_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"unable to read HEAD: {exc}") from exc

    if not content.startswith(_HEAD_REF_PREFIX):
        raise ValueError("detached or unsupported HEAD state")

    ref_name = content[len(_HEAD_REF_PREFIX) :]
    if not ref_name.startswith(_LOCAL_HEAD_PREFIX):
        raise ValueError("HEAD must reference refs/heads/*")
    return ref_name


def read_branch_tip(ref_path: Path) -> str | None:
    """Read a branch ref object id if present and valid."""

    if not ref_path.exists():
        return None

    try:
        value = ref_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"unable to read branch ref: {exc}") from exc

    if not value:
        return None
    if not is_valid_object_id(value):
        raise ValueError("branch ref contains invalid object id")
    return value


def read_head_commit_oid(head_path: Path, git_dir: Path) -> str | None:
    """Resolve HEAD symbolic ref and return its current branch tip oid."""

    head_ref = read_current_head_ref(head_path)
    return read_branch_tip(git_dir / head_ref)


def persist_ref_atomic(ref_path: Path, object_id: str) -> None:
    """Persist a branch ref update atomically with deterministic content."""

    if not is_valid_object_id(object_id):
        raise ValueError(f"invalid object id: {object_id}")

    ref_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=ref_path.parent,
            prefix=f".{ref_path.name}.tmp-",
            delete=False,
        ) as tmp_file:
            tmp_file.write(f"{object_id}\n")
            temp_path = Path(tmp_file.name)
        os.replace(temp_path, ref_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
