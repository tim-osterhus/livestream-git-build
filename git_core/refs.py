#!/usr/bin/env python3
"""Reference bootstrap helpers for repository initialization."""

from __future__ import annotations

from repo import RepoPaths

DEFAULT_BRANCH = "main"
DEFAULT_HEAD_REF = f"refs/heads/{DEFAULT_BRANCH}"
DEFAULT_HEAD_CONTENT = f"ref: {DEFAULT_HEAD_REF}\n"


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

