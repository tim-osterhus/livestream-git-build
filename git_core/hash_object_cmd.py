#!/usr/bin/env python3
"""`hash-object` command implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

from objects import compute_object_id, serialize_blob, write_loose_object
from repo import discover_repo_paths

HASH_OBJECT_USAGE = "usage: run_git hash-object -w <path>\n"


def _print_usage(stream: object) -> None:
    stream.write(HASH_OBJECT_USAGE)


def _resolve_input_path(path_arg: str, cwd: str | Path | None) -> Path:
    base_dir = Path(cwd).resolve() if cwd is not None else Path.cwd()
    return (base_dir / path_arg).resolve()


def run_hash_object(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Write a blob object for `hash-object -w <path>` and print its oid."""

    if len(args) != 2 or args[0] != "-w":
        sys.stderr.write("run_git: hash-object requires exactly '-w <path>'.\n")
        _print_usage(sys.stderr)
        return 2

    input_path = _resolve_input_path(args[1], cwd)
    if not input_path.is_file():
        sys.stderr.write(f"run_git: hash-object: file not found: {args[1]}\n")
        return 1

    paths = discover_repo_paths(cwd)
    if not paths.git_dir.is_dir():
        sys.stderr.write("run_git: hash-object: not a git repository (missing .git).\n")
        return 1

    payload = input_path.read_bytes()
    serialized = serialize_blob(payload)
    object_id = compute_object_id(serialized)
    write_loose_object(paths.objects_dir, object_id, serialized)
    sys.stdout.write(f"{object_id}\n")
    return 0
