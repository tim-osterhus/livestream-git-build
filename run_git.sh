#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CLI_PY="$SCRIPT_DIR/git_core/cli.py"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "run_git: python interpreter '$PYTHON_BIN' not found" >&2
  exit 127
fi

if [[ $# -eq 0 ]]; then
  exec "$PYTHON_BIN" "$CLI_PY" --help
fi

subcommand="$1"
shift

case "$subcommand" in
  -h|--help|help)
    exec "$PYTHON_BIN" "$CLI_PY" --help
    ;;
  init|hash-object|cat-file|add|commit|log|status|diff|branch|checkout|tag)
    exec "$PYTHON_BIN" "$CLI_PY" "$subcommand" "$@"
    ;;
  *)
    exec "$PYTHON_BIN" "$CLI_PY" "$subcommand" "$@"
    ;;
esac
