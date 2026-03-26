#!/usr/bin/env python3
"""Dispatch scaffold for the staged git implementation."""

from __future__ import annotations

import sys
from typing import Callable, Sequence

USAGE_TEXT = """usage: run_git <command> [<args>]

Implemented command handlers in this phase:
  init
  hash-object
  cat-file

Known command floor (pending later phases):
  add
  commit
  log
  status
  diff
  branch
  checkout
  tag
"""

KNOWN_FLOOR_COMMANDS = {
    "init",
    "hash-object",
    "cat-file",
    "add",
    "commit",
    "log",
    "status",
    "diff",
    "branch",
    "checkout",
    "tag",
}


def _print_usage(stream: object) -> None:
    stream.write(USAGE_TEXT)


def _not_implemented(command: str) -> int:
    sys.stderr.write(
        f"run_git: subcommand '{command}' handler is scaffolded but not implemented yet.\n"
    )
    return 3


def handle_init(args: Sequence[str]) -> int:
    _ = args
    return _not_implemented("init")


def handle_hash_object(args: Sequence[str]) -> int:
    _ = args
    return _not_implemented("hash-object")


def handle_cat_file(args: Sequence[str]) -> int:
    _ = args
    return _not_implemented("cat-file")


COMMAND_HANDLERS: dict[str, Callable[[Sequence[str]], int]] = {
    "init": handle_init,
    "hash-object": handle_hash_object,
    "cat-file": handle_cat_file,
}


def dispatch(argv: Sequence[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_usage(sys.stdout)
        return 0

    command, *command_args = argv

    if command in COMMAND_HANDLERS:
        return COMMAND_HANDLERS[command](command_args)

    if command in KNOWN_FLOOR_COMMANDS:
        sys.stderr.write(
            f"run_git: subcommand '{command}' is recognized but not implemented in this phase.\n"
        )
        _print_usage(sys.stderr)
        return 2

    sys.stderr.write(f"run_git: unknown subcommand '{command}'.\n")
    _print_usage(sys.stderr)
    return 2


def main() -> int:
    return dispatch(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
