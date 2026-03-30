#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
CANDIDATE="$REPO_ROOT/run_git.sh"

# shellcheck source=staging/tests/helpers/assertions.sh
source "$SCRIPT_DIR/helpers/assertions.sh"

workdir="$(mktemp -d)"
cleanup() {
  rm -rf -- "$workdir"
}
trap cleanup EXIT

cd "$workdir"

"$CANDIDATE" init >/dev/null

printf 'alpha\n' > hello.txt
"$CANDIDATE" add hello.txt >/dev/null

subject_one='phase02 smoke commit'
"$CANDIDATE" commit -m "$subject_one" >/dev/null

candidate_subject_one="$("$CANDIDATE" log --max-count=1)"
host_subject_one="$(git log --format=%s -1)"

assert_equals "$subject_one" "$candidate_subject_one" 'candidate log subject (first commit)'
assert_equals "$subject_one" "$host_subject_one" 'host git log subject (first commit)'
assert_equals "$host_subject_one" "$candidate_subject_one" 'candidate/host subject parity (first commit)'

printf 'beta\n' >> hello.txt
"$CANDIDATE" add hello.txt >/dev/null

subject_two='phase02 smoke commit follow-up'
"$CANDIDATE" commit -m "$subject_two" >/dev/null

candidate_subject_two="$("$CANDIDATE" log --max-count=1)"
host_subject_two="$(git log --format=%s -1)"

assert_equals "$subject_two" "$candidate_subject_two" 'candidate log subject (latest commit)'
assert_equals "$subject_two" "$host_subject_two" 'host git log subject (latest commit)'
assert_equals "$host_subject_two" "$candidate_subject_two" 'candidate/host subject parity (latest commit)'

candidate_history_two="$("$CANDIDATE" log --max-count=2)"
host_history_two="$(git log --format=%s -2)"
assert_equals "$host_history_two" "$candidate_history_two" 'candidate/host two-commit subject history parity'

printf 'smoke_phase02: PASS\n'
