#!/usr/bin/env python3
"""`log` command implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence
import zlib

from objects import is_valid_object_id, read_object
from refs import read_head_commit_oid
from repo import discover_repo_paths

LOG_USAGE = "usage: run_git log --max-count=<n>\n"
_MAX_COUNT_PREFIX = "--max-count="


def _print_usage(stream: object) -> None:
    stream.write(LOG_USAGE)


def _parse_log_args(args: Sequence[str]) -> int:
    if len(args) != 1 or not args[0].startswith(_MAX_COUNT_PREFIX):
        raise ValueError("log requires exactly '--max-count=<n>'")

    raw_value = args[0][len(_MAX_COUNT_PREFIX) :]
    if not raw_value or not raw_value.isdigit():
        raise ValueError("max-count must be a non-negative integer")

    return int(raw_value, 10)


def _parse_commit_body(body: bytes) -> tuple[str | None, str]:
    try:
        payload = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("commit payload is not valid UTF-8") from exc

    lines = payload.split("\n")
    index = 0
    parents: list[str] = []

    while index < len(lines):
        line = lines[index]
        if line == "":
            index += 1
            break
        if line.startswith("parent "):
            parent_oid = line[len("parent ") :].strip()
            if not is_valid_object_id(parent_oid):
                raise ValueError("commit contains invalid parent object id")
            parents.append(parent_oid)
        index += 1
    else:
        raise ValueError("commit missing header/message separator")

    if len(parents) > 1:
        raise ValueError("merge commits are not supported in this phase")

    subject = ""
    while index < len(lines):
        if lines[index]:
            subject = lines[index]
            break
        index += 1

    if not subject:
        raise ValueError("commit subject is missing")

    parent_oid = parents[0] if parents else None
    return parent_oid, subject


def _read_commit_metadata(objects_dir: Path, object_id: str) -> tuple[str | None, str]:
    try:
        kind, body = read_object(objects_dir, object_id)
    except FileNotFoundError as exc:
        raise ValueError(f"object not found: {object_id}") from exc
    except zlib.error as exc:
        raise ValueError(f"unable to decode object '{object_id}'") from exc
    except OSError as exc:
        raise ValueError(f"unable to read object '{object_id}': {exc}") from exc

    if kind != "commit":
        raise ValueError(f"object '{object_id}' is not a commit")

    return _parse_commit_body(body)


def run_log(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Print commit subjects while traversing parent links from HEAD."""

    try:
        max_count = _parse_log_args(args)
    except ValueError as exc:
        sys.stderr.write(f"run_git: log: {exc}\n")
        _print_usage(sys.stderr)
        return 2

    repo_paths = discover_repo_paths(cwd)
    if not repo_paths.git_dir.is_dir():
        sys.stderr.write("run_git: log: not a git repository (missing .git).\n")
        return 1

    try:
        current_oid = read_head_commit_oid(repo_paths.head_file, repo_paths.git_dir)
    except ValueError as exc:
        sys.stderr.write(f"run_git: log: {exc}\n")
        return 1

    if current_oid is None or max_count == 0:
        return 0

    subjects: list[str] = []
    visited: set[str] = set()
    try:
        while current_oid is not None and len(subjects) < max_count:
            if current_oid in visited:
                raise ValueError("detected commit parent cycle")
            visited.add(current_oid)

            parent_oid, subject = _read_commit_metadata(repo_paths.objects_dir, current_oid)
            subjects.append(subject)
            current_oid = parent_oid
    except ValueError as exc:
        sys.stderr.write(f"run_git: log: {exc}\n")
        return 1

    if subjects:
        sys.stdout.write("\n".join(subjects))
        sys.stdout.write("\n")
    return 0
