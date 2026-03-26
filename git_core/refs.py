#!/usr/bin/env python3
"""Reference bootstrap and ref I/O helpers."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

from objects import is_valid_object_id
from repo import RepoPaths

DEFAULT_BRANCH = "main"
DEFAULT_HEAD_REF = f"refs/heads/{DEFAULT_BRANCH}"
_HEAD_REF_PREFIX = "ref: "
_LOCAL_HEAD_PREFIX = "refs/heads/"
_TAG_REF_PREFIX = "refs/tags/"
_REF_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _is_local_branch_symbolic_ref(content: str) -> bool:
    return content.startswith(f"{_HEAD_REF_PREFIX}{_LOCAL_HEAD_PREFIX}")


def _validate_ref_suffix(ref_suffix: str, label: str) -> str:
    if not ref_suffix:
        raise ValueError(f"{label} name must not be empty")

    for segment in ref_suffix.split("/"):
        if not _REF_SEGMENT_PATTERN.fullmatch(segment):
            raise ValueError(f"invalid {label} name '{ref_suffix}'")
    return ref_suffix


def _validate_branch_ref_name(ref_name: str) -> str:
    if not ref_name.startswith(_LOCAL_HEAD_PREFIX):
        raise ValueError("branch ref must start with refs/heads/")
    _validate_ref_suffix(ref_name[len(_LOCAL_HEAD_PREFIX) :], "branch")
    return ref_name


def _validate_tag_ref_name(ref_name: str) -> str:
    if not ref_name.startswith(_TAG_REF_PREFIX):
        raise ValueError("tag ref must start with refs/tags/")
    _validate_ref_suffix(ref_name[len(_TAG_REF_PREFIX) :], "tag")
    return ref_name


def _persist_text_atomic(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
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
    _validate_ref_suffix(ref_name[len(_LOCAL_HEAD_PREFIX) :], "branch")
    return ref_name


def read_ref_tip(ref_path: Path, label: str) -> str | None:
    """Read an object id from a ref file if present and valid."""

    if not ref_path.exists():
        return None

    try:
        value = ref_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"unable to read {label} ref: {exc}") from exc

    if not value:
        return None
    if not is_valid_object_id(value):
        raise ValueError(f"{label} ref contains invalid object id")
    return value


def read_branch_tip(ref_path: Path) -> str | None:
    """Read a branch tip object id from a refs/heads path."""

    return read_ref_tip(ref_path, label="branch")


def read_tag_tip(ref_path: Path) -> str | None:
    """Read a tag tip object id from a refs/tags path."""

    return read_ref_tip(ref_path, label="tag")


def read_branch_tip_by_name(paths: RepoPaths, branch_name: str) -> str | None:
    """Read branch tip by short branch name (for example `main`)."""

    safe_name = _validate_ref_suffix(branch_name, "branch")
    _validate_branch_ref_name(f"{_LOCAL_HEAD_PREFIX}{safe_name}")
    return read_branch_tip(paths.branch_ref_path(safe_name))


def read_tag_tip_by_name(paths: RepoPaths, tag_name: str) -> str | None:
    """Read tag tip by short tag name (for example `v0.1.0`)."""

    safe_name = _validate_ref_suffix(tag_name, "tag")
    _validate_tag_ref_name(f"{_TAG_REF_PREFIX}{safe_name}")
    return read_tag_tip(paths.tag_ref_path(safe_name))


def resolve_head_ref_path(paths: RepoPaths) -> Path:
    """Resolve symbolic HEAD to its branch ref path."""

    return paths.ref_path(read_current_head_ref(paths.head_file))


def read_head_commit_oid(head_path: Path, git_dir: Path) -> str | None:
    """Resolve HEAD symbolic ref and return its current branch tip oid."""

    head_ref = read_current_head_ref(head_path)
    return read_ref_tip(git_dir / head_ref, label="branch")


def persist_ref_atomic(ref_path: Path, object_id: str) -> None:
    """Persist a branch ref update atomically with deterministic content."""

    if not is_valid_object_id(object_id):
        raise ValueError(f"invalid object id: {object_id}")

    _persist_text_atomic(ref_path, f"{object_id}\n")


def persist_head_symbolic_ref_atomic(head_path: Path, branch_ref: str) -> None:
    """Persist `HEAD` as a symbolic local branch ref atomically."""

    _validate_branch_ref_name(branch_ref)
    _persist_text_atomic(head_path, f"{_HEAD_REF_PREFIX}{branch_ref}\n")


def ensure_init_ref_layout(paths: RepoPaths) -> None:
    """Create required ref namespaces and initialize HEAD deterministically."""

    paths.refs_dir.mkdir(parents=True, exist_ok=True)
    paths.heads_dir.mkdir(parents=True, exist_ok=True)
    paths.tags_dir.mkdir(parents=True, exist_ok=True)

    if not paths.head_file.exists():
        persist_head_symbolic_ref_atomic(paths.head_file, DEFAULT_HEAD_REF)
        return

    head_content = paths.head_file.read_text(encoding="utf-8")
    if _is_local_branch_symbolic_ref(head_content):
        return
