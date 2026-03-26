#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
CANDIDATE="$REPO_ROOT/staging/run_git.sh"

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

subject='phase02 smoke commit'
"$CANDIDATE" commit -m "$subject" >/dev/null

candidate_subject="$("$CANDIDATE" log --max-count=1)"
host_subject="$(git log --format=%s -1)"

assert_equals "$subject" "$candidate_subject" 'candidate log subject'
assert_equals "$subject" "$host_subject" 'host git log subject'

printf 'smoke_phase02: PASS\n'
