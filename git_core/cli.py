#!/usr/bin/env python3
"""Dispatch scaffold for the staged git implementation."""

from __future__ import annotations

import sys
from typing import Callable, Sequence

from add_cmd import run_add
from branch_cmd import run_branch
from cat_file_cmd import run_cat_file
from checkout_cmd import run_checkout
from commit_cmd import run_commit
from diff_cmd import run_diff
from hash_object_cmd import run_hash_object
from init_cmd import run_init
from log_cmd import run_log
from status_cmd import run_status
from tag_cmd import run_tag

USAGE_TEXT = """usage: run_git <command> [<args>]

Implemented command handlers in this phase:
  init
  hash-object
  cat-file
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


def _deferred_phase_stub(command: str) -> int:
    sys.stderr.write(
        f"run_git: subcommand '{command}' is recognized but not implemented in this phase.\n"
    )
    _print_usage(sys.stderr)
    return 2


def handle_init(args: Sequence[str]) -> int:
    if args:
        sys.stderr.write("run_git: init does not accept positional arguments.\n")
        _print_usage(sys.stderr)
        return 2
    return run_init()


def handle_hash_object(args: Sequence[str]) -> int:
    return run_hash_object(args)


def handle_cat_file(args: Sequence[str]) -> int:
    return run_cat_file(args)


def handle_add(args: Sequence[str]) -> int:
    return run_add(args)


def handle_commit(args: Sequence[str]) -> int:
    return run_commit(args)


def handle_log(args: Sequence[str]) -> int:
    return run_log(args)


def handle_status(args: Sequence[str]) -> int:
    return run_status(args)


def handle_diff(args: Sequence[str]) -> int:
    return run_diff(args)


def handle_branch(args: Sequence[str]) -> int:
    return run_branch(args)


def handle_checkout(args: Sequence[str]) -> int:
    return run_checkout(args)


def handle_tag(args: Sequence[str]) -> int:
    return run_tag(args)


COMMAND_HANDLERS: dict[str, Callable[[Sequence[str]], int]] = {
    "init": handle_init,
    "hash-object": handle_hash_object,
    "cat-file": handle_cat_file,
    "add": handle_add,
    "commit": handle_commit,
    "log": handle_log,
    "status": handle_status,
    "diff": handle_diff,
    "branch": handle_branch,
    "checkout": handle_checkout,
    "tag": handle_tag,
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
