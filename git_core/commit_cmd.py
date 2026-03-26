#!/usr/bin/env python3
"""`commit` command implementation."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Sequence

from index import index_file_path, load_index
from objects import compute_object_id, serialize_commit, write_loose_object
from refs import persist_ref_atomic, read_branch_tip, read_current_head_ref
from repo import discover_repo_paths
from tree import write_tree_from_index

COMMIT_USAGE = "usage: run_git commit -m <message>\n"
_COMMIT_DATE_PATTERN = re.compile(r"^\d+ [+-]\d{4}$")
_DEFAULT_COMMITTER_NAME = "run_git"
_DEFAULT_COMMITTER_EMAIL = "run_git@example.com"
_DEFAULT_COMMITTER_DATE = "0 +0000"


def _print_usage(stream: object) -> None:
    stream.write(COMMIT_USAGE)


def _parse_commit_args(args: Sequence[str]) -> str:
    if len(args) != 2 or args[0] != "-m":
        raise ValueError("commit requires exactly '-m <message>'")
    if not args[1]:
        raise ValueError("commit message must not be empty")
    return args[1]


def _resolve_identity(name_env: str, email_env: str, date_env: str) -> tuple[str, str, str]:
    name = os.environ.get(name_env) or os.environ.get("GIT_COMMITTER_NAME") or _DEFAULT_COMMITTER_NAME
    email = os.environ.get(email_env) or os.environ.get("GIT_COMMITTER_EMAIL") or _DEFAULT_COMMITTER_EMAIL

    raw_date = os.environ.get(date_env, "").strip()
    if raw_date and _COMMIT_DATE_PATTERN.fullmatch(raw_date):
        date_value = raw_date
    elif raw_date and raw_date.isdigit():
        date_value = f"{raw_date} +0000"
    else:
        date_value = _DEFAULT_COMMITTER_DATE

    return name, email, date_value


def _build_commit_object(tree_oid: str, parent_oid: str | None, message: str) -> bytes:
    author_name, author_email, author_date = _resolve_identity(
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE"
    )
    committer_name, committer_email, committer_date = _resolve_identity(
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE"
    )
    return serialize_commit(
        tree_oid,
        parent_oid,
        (author_name, author_email, author_date),
        (committer_name, committer_email, committer_date),
        message,
    )


def run_commit(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Create a commit from the current staged snapshot and update HEAD branch ref."""

    try:
        message = _parse_commit_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: commit: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: commit: not a git repository (missing .git).\n")
        return 1

    idx_path = index_file_path(repo_paths.git_dir)
    try:
        staged_entries = load_index(idx_path)
    except ValueError as exc:
        sys.stderr.write(f"run_git: commit: invalid index: {exc}\n")
        return 1

    if not staged_entries:
        sys.stderr.write("run_git: commit: nothing to commit (index is empty).\n")
        return 1

    try:
        head_ref = read_current_head_ref(repo_paths.head_file)
        head_ref_path = repo_paths.git_dir / head_ref
        parent_oid = read_branch_tip(head_ref_path)
        tree_oid = write_tree_from_index(repo_paths.objects_dir, staged_entries)
        serialized = _build_commit_object(tree_oid, parent_oid, message)
    except ValueError as exc:
        sys.stderr.write(f"run_git: commit: {exc}\n")
        return 1

    commit_oid = compute_object_id(serialized)
    write_loose_object(repo_paths.objects_dir, commit_oid, serialized)

    try:
        persist_ref_atomic(head_ref_path, commit_oid)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"run_git: commit: unable to update branch ref: {exc}\n")
        return 1

    sys.stdout.write(f"{commit_oid}\n")
    return 0
