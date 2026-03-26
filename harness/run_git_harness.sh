#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

CANDIDATE=""
WORKDIR="$REPO_ROOT/artifacts/git-harness"
MODE="core"
QUIET=0

SUMMARY_TSV=""
SUMMARY_MD=""
SUMMARY_JSON=""
LOG_DIR=""
SUITE_FAILURES=0

usage() {
  cat <<USAGE
Usage:
  $SCRIPT_NAME --candidate /absolute/path/to/run_git.sh [--workdir DIR] [--mode MODE]

Modes:
  core         must-have local Git floor
  interop      host-git interoperability round-trip
  merge        basic non-conflicting merge proof
  blog_floor   core + interop + merge
  repo_stretch blog_floor + reflog/ref-management stretch checks
USAGE
}

log() {
  local level="$1"
  shift
  if [ "$QUIET" = "1" ] && [ "$level" = "INFO" ]; then
    return 0
  fi
  printf '[%s] %s\n' "$level" "$*" >&2
}

info() { log INFO "$@"; }
error() { log ERROR "$@"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    error "missing required command: $1"
    exit 2
  }
}

run_candidate() {
  local repo="$1"
  shift
  (
    cd "$repo"
    GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-Millrace Harness}" \
    GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-millrace@example.com}" \
    GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-Millrace Harness}" \
    GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-millrace@example.com}" \
    "$CANDIDATE" "$@"
  )
}

capture_candidate() {
  local repo="$1"
  shift
  run_candidate "$repo" "$@"
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  case "$haystack" in
    *"$needle"*) ;;
    *)
      error "expected output to contain: $needle"
      return 1
      ;;
  esac
}

prepare_repo() {
  local repo="$1"
  mkdir -p "$repo"
  git -C "$repo" init >/dev/null 2>&1 || true
}

configure_identity() {
  local repo="$1"
  git -C "$repo" config user.name "Millrace Harness"
  git -C "$repo" config user.email "millrace@example.com"
}

current_branch() {
  local repo="$1"
  git -C "$repo" symbolic-ref --quiet --short HEAD
}

record_result() {
  local suite="$1"
  local status="$2"
  local detail="$3"
  local logfile="$4"
  printf '%s\t%s\t%s\t%s\n' "$suite" "$status" "$detail" "$logfile" >>"$SUMMARY_TSV"
  if [ "$status" = "FAIL" ]; then
    SUITE_FAILURES=$((SUITE_FAILURES + 1))
  fi
}

make_summary_markdown() {
  {
    echo "# Git Harness Summary"
    echo
    echo "- Candidate: \`$CANDIDATE\`"
    echo "- Workdir: \`$WORKDIR\`"
    echo "- Mode: \`$MODE\`"
    echo
    echo "| Suite | Status | Detail | Log |"
    echo "|---|---|---|---|"
    while IFS=$'\t' read -r suite status detail logfile; do
      printf '| %s | %s | %s | `%s` |\n' "$suite" "$status" "$detail" "$logfile"
    done < "$SUMMARY_TSV"
    echo
    echo "- Suite failures: $SUITE_FAILURES"
  } >"$SUMMARY_MD"
}

make_summary_json() {
  python3 - "$SUMMARY_TSV" "$SUMMARY_JSON" "$CANDIDATE" "$WORKDIR" "$MODE" "$SUITE_FAILURES" <<'PY'
import json
import sys
from pathlib import Path

tsv_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
candidate = sys.argv[3]
workdir = sys.argv[4]
mode = sys.argv[5]
suite_failures = int(sys.argv[6])

entries = []
for line in tsv_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    suite, status, detail, logfile = line.split("\t", 3)
    entries.append(
        {
            "suite": suite,
            "status": status,
            "detail": detail,
            "log": logfile
        }
    )

payload = {
    "schema_version": "1.0",
    "candidate": candidate,
    "workdir": workdir,
    "mode": mode,
    "suite_failures": suite_failures,
    "suites": entries
}

json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

run_suite() {
  local suite="$1"
  shift
  local logfile="$LOG_DIR/$suite.log"
  if "$@" >"$logfile" 2>&1; then
    record_result "$suite" "PASS" "ok" "$logfile"
    info "suite passed: $suite"
  else
    record_result "$suite" "FAIL" "see log" "$logfile"
    error "suite failed: $suite"
  fi
}

suite_core() {
  local repo="$WORKDIR/core/repo"
  local oid status_output diff_output log_output default_branch

  mkdir -p "$repo"
  run_candidate "$repo" init
  [ -f "$repo/.git/HEAD" ]
  configure_identity "$repo"

  printf 'alpha\n' >"$repo/hello.txt"
  status_output="$(capture_candidate "$repo" status)"
  assert_contains "$status_output" "hello.txt"

  oid="$(capture_candidate "$repo" hash-object -w hello.txt | tr -d '\r' | tail -n 1)"
  [ -n "$oid" ]
  assert_contains "$(capture_candidate "$repo" cat-file -p "$oid")" "alpha"
  assert_contains "$(git -C "$repo" cat-file -p "$oid")" "alpha"

  run_candidate "$repo" add hello.txt
  run_candidate "$repo" commit -m "initial commit"
  log_output="$(capture_candidate "$repo" log --max-count=1)"
  assert_contains "$log_output" "initial commit"

  default_branch="$(current_branch "$repo")"
  [ -n "$default_branch" ]
  run_candidate "$repo" branch feature
  run_candidate "$repo" checkout feature
  printf 'beta\n' >>"$repo/hello.txt"
  status_output="$(capture_candidate "$repo" status)"
  assert_contains "$status_output" "hello.txt"
  diff_output="$(capture_candidate "$repo" diff)"
  assert_contains "$diff_output" "beta"
  run_candidate "$repo" add hello.txt
  run_candidate "$repo" commit -m "feature update"
  run_candidate "$repo" tag v0.1.0
  run_candidate "$repo" checkout "$default_branch"

  [ "$(current_branch "$repo")" = "$default_branch" ]
  git -C "$repo" show-ref --verify --quiet refs/heads/feature
  git -C "$repo" show-ref --verify --quiet refs/tags/v0.1.0
}

suite_interop() {
  local repo="$WORKDIR/interop/repo"
  local default_branch log_output

  mkdir -p "$repo"
  run_candidate "$repo" init
  configure_identity "$repo"
  printf 'first\n' >"$repo/notes.txt"
  run_candidate "$repo" add notes.txt
  run_candidate "$repo" commit -m "candidate base commit"

  assert_contains "$(git -C "$repo" log --format=%s -1)" "candidate base commit"

  default_branch="$(current_branch "$repo")"
  git -C "$repo" checkout -b host-side >/dev/null 2>&1
  printf 'host line\n' >>"$repo/notes.txt"
  git -C "$repo" add notes.txt
  GIT_AUTHOR_NAME="Host Git" \
  GIT_AUTHOR_EMAIL="host@example.com" \
  GIT_COMMITTER_NAME="Host Git" \
  GIT_COMMITTER_EMAIL="host@example.com" \
  git -C "$repo" commit -m "host side commit" >/dev/null
  log_output="$(capture_candidate "$repo" log --max-count=2)"
  assert_contains "$log_output" "host side commit"
  git -C "$repo" checkout "$default_branch" >/dev/null 2>&1
}

suite_merge() {
  local repo="$WORKDIR/merge/repo"
  local default_branch

  mkdir -p "$repo"
  run_candidate "$repo" init
  configure_identity "$repo"
  printf 'base\n' >"$repo/base.txt"
  run_candidate "$repo" add base.txt
  run_candidate "$repo" commit -m "base commit"
  default_branch="$(current_branch "$repo")"

  run_candidate "$repo" branch feature
  run_candidate "$repo" checkout feature
  printf 'feature change\n' >"$repo/feature.txt"
  run_candidate "$repo" add feature.txt
  run_candidate "$repo" commit -m "feature commit"

  run_candidate "$repo" checkout "$default_branch"
  printf 'main change\n' >"$repo/main.txt"
  run_candidate "$repo" add main.txt
  run_candidate "$repo" commit -m "main commit"

  run_candidate "$repo" merge feature

  assert_contains "$(cat "$repo/feature.txt")" "feature change"
  assert_contains "$(cat "$repo/main.txt")" "main change"
  if grep -R "<<<<<<<\\|=======\\|>>>>>>>" "$repo" >/dev/null 2>&1; then
    error "merge left conflict markers"
    return 1
  fi
  [ -z "$(git -C "$repo" status --porcelain)" ]
  [ "$(git -C "$repo" rev-list --parents -n 1 HEAD | awk '{print NF}')" = "3" ]
}

suite_reflog() {
  local repo="$WORKDIR/repo_stretch/repo"
  local default_branch reflog_output

  mkdir -p "$repo"
  run_candidate "$repo" init
  configure_identity "$repo"
  printf 'seed\n' >"$repo/reflog.txt"
  run_candidate "$repo" add reflog.txt
  run_candidate "$repo" commit -m "seed commit"
  default_branch="$(current_branch "$repo")"
  run_candidate "$repo" branch feature
  run_candidate "$repo" checkout feature
  run_candidate "$repo" checkout "$default_branch"
  reflog_output="$(capture_candidate "$repo" reflog)"
  assert_contains "$reflog_output" "$default_branch"
}

while (($# > 0)); do
  case "$1" in
    --candidate)
      CANDIDATE="${2:?missing value for --candidate}"
      shift 2
      ;;
    --workdir)
      WORKDIR="${2:?missing value for --workdir}"
      shift 2
      ;;
    --mode)
      MODE="${2:?missing value for --mode}"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[ -n "$CANDIDATE" ] || {
  usage >&2
  exit 2
}

case "$MODE" in
  core|interop|merge|blog_floor|repo_stretch) ;;
  *)
    echo "error: unsupported mode: $MODE" >&2
    exit 2
    ;;
esac

need_cmd git
need_cmd python3

[ -x "$CANDIDATE" ] || {
  error "candidate entrypoint must exist and be executable: $CANDIDATE"
  exit 2
}

rm -rf -- "$WORKDIR"
mkdir -p "$WORKDIR"
LOG_DIR="$WORKDIR/logs"
mkdir -p "$LOG_DIR"
SUMMARY_TSV="$WORKDIR/summary.tsv"
SUMMARY_MD="$WORKDIR/summary.md"
SUMMARY_JSON="$WORKDIR/summary.json"
: >"$SUMMARY_TSV"

info "running git harness mode=$MODE candidate=$CANDIDATE"

case "$MODE" in
  core)
    run_suite core suite_core
    ;;
  interop)
    run_suite interop suite_interop
    ;;
  merge)
    run_suite merge suite_merge
    ;;
  blog_floor)
    run_suite core suite_core
    run_suite interop suite_interop
    run_suite merge suite_merge
    ;;
  repo_stretch)
    run_suite core suite_core
    run_suite interop suite_interop
    run_suite merge suite_merge
    run_suite repo_stretch suite_reflog
    ;;
esac

make_summary_markdown
make_summary_json

if [ "$SUITE_FAILURES" -ne 0 ]; then
  error "git harness completed with failures=$SUITE_FAILURES"
  exit 1
fi

info "git harness completed successfully"
