#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
CANDIDATE="$REPO_ROOT/run_git.sh"

# shellcheck source=staging/tests/helpers/assertions.sh
source "$SCRIPT_DIR/helpers/assertions.sh"

workdir="$(mktemp -d)"
merge_stderr="$(mktemp)"
cleanup() {
  rm -rf -- "$workdir"
  rm -f -- "$merge_stderr"
}
trap cleanup EXIT

cd "$workdir"

"$CANDIDATE" init >/dev/null

printf 'base\n' > base.txt
"$CANDIDATE" add base.txt >/dev/null
"$CANDIDATE" commit -m base >/dev/null

"$CANDIDATE" branch feature >/dev/null

printf 'main-line\n' > main.txt
"$CANDIDATE" add main.txt >/dev/null
"$CANDIDATE" commit -m main >/dev/null

"$CANDIDATE" checkout feature >/dev/null
printf 'feature-line\n' > feature.txt
"$CANDIDATE" add feature.txt >/dev/null
"$CANDIDATE" commit -m feature >/dev/null

"$CANDIDATE" checkout main >/dev/null

set +e
"$CANDIDATE" merge feature >/dev/null 2>"$merge_stderr"
merge_exit=$?
set -e

if [[ "$merge_exit" -ne 0 ]]; then
  fail "expected non-conflicting merge to exit 0 but got $merge_exit (stderr: $(cat "$merge_stderr"))"
fi

status_porcelain="$(git status --porcelain)"
assert_equals "" "$status_porcelain" 'host git porcelain status after merge'

head_parents="$(git rev-list --parents -n 1 HEAD)"
assert_word_count "3" "$head_parents" 'rev-list --parents -n 1 HEAD output'

if rg -n '<<<<<<<|=======|>>>>>>>' . --hidden --glob '!.git/**' >/dev/null 2>&1; then
  fail 'expected no conflict markers in working tree files'
fi

printf 'smoke_merge_phase02: PASS\n'
