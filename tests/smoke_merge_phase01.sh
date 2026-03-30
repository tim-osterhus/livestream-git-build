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
"$CANDIDATE" merge feature >/tmp/smoke_merge_phase01.out 2>/tmp/smoke_merge_phase01.err
merge_exit=$?
set -e

if [[ "$merge_exit" -ne 0 ]]; then
  fail "expected non-conflicting merge to exit 0 but got $merge_exit"
fi

head_parents="$(git rev-list --parents -n 1 HEAD)"
assert_word_count "3" "$head_parents" "rev-list --parents -n 1 HEAD output"

printf 'smoke_merge_phase01: PASS\n'
