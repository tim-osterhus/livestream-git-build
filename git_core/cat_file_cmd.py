#!/usr/bin/env python3
"""`cat-file` command implementation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence
import zlib

from objects import is_valid_object_id, read_object
from repo import discover_repo_paths

CAT_FILE_USAGE = "usage: run_git cat-file -p <object>\n"


def _print_usage(stream: object) -> None:
    stream.write(CAT_FILE_USAGE)


def run_cat_file(args: Sequence[str], cwd: str | Path | None = None) -> int:
    """Print decoded blob payload bytes for `cat-file -p <oid>`."""

    if len(args) != 2 or args[0] != "-p":
        sys.stderr.write("run_git: cat-file requires exactly '-p <object>'.\n")
        _print_usage(sys.stderr)
        return 2

    object_id = args[1]
    if not is_valid_object_id(object_id):
        sys.stderr.write(f"run_git: cat-file: invalid object id: {object_id}\n")
        return 1

    paths = discover_repo_paths(cwd)
    if not paths.git_dir.is_dir():
        sys.stderr.write("run_git: cat-file: not a git repository (missing .git).\n")
        return 1

    try:
        object_type, body = read_object(paths.objects_dir, object_id)
    except FileNotFoundError:
        sys.stderr.write(f"run_git: cat-file: object not found: {object_id}\n")
        return 1
    except (ValueError, OSError, RuntimeError, EOFError, zlib.error):
        sys.stderr.write(f"run_git: cat-file: unable to decode object: {object_id}\n")
        return 1

    if object_type != "blob":
        sys.stderr.write(f"run_git: cat-file: unsupported object type: {object_type}\n")
        return 1

    sys.stdout.buffer.write(body)
    return 0
