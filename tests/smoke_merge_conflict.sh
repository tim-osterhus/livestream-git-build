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

printf 'base\n' > same.txt
"$CANDIDATE" add same.txt >/dev/null
"$CANDIDATE" commit -m base >/dev/null

"$CANDIDATE" branch feature >/dev/null

printf 'main-change\n' > same.txt
"$CANDIDATE" add same.txt >/dev/null
"$CANDIDATE" commit -m main-change >/dev/null

"$CANDIDATE" checkout feature >/dev/null
printf 'feature-change\n' > same.txt
"$CANDIDATE" add same.txt >/dev/null
"$CANDIDATE" commit -m feature-change >/dev/null

"$CANDIDATE" checkout main >/dev/null

head_before="$(git rev-parse HEAD)"

set +e
"$CANDIDATE" merge feature >/tmp/smoke_merge_conflict.out 2>/tmp/smoke_merge_conflict.err
merge_exit=$?
set -e

if [[ "$merge_exit" -eq 0 ]]; then
  fail "expected conflicting merge to exit non-zero"
fi

head_after="$(git rev-parse HEAD)"
assert_equals "$head_before" "$head_after" 'HEAD oid after conflicting merge'

if rg -n '<<<<<<<|=======|>>>>>>>' . --hidden --glob '!.git/**' >/dev/null 2>&1; then
  fail 'expected no conflict markers in working tree files'
fi

printf 'smoke_merge_conflict: PASS\n'
