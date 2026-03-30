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

assert_dir_exists .git
assert_dir_exists .git/objects
assert_dir_exists .git/refs
assert_dir_exists .git/refs/heads
assert_dir_exists .git/refs/tags
assert_file_exists .git/HEAD

printf 'alpha\n' > hello.txt
oid="$($CANDIDATE hash-object -w hello.txt)"
assert_match "$oid" '^[0-9a-f]{40}$' 'blob oid'

"$CANDIDATE" cat-file -p "$oid" > candidate_blob.txt
git cat-file -p "$oid" > system_blob.txt

assert_files_equal hello.txt candidate_blob.txt
assert_files_equal hello.txt system_blob.txt
assert_files_equal candidate_blob.txt system_blob.txt

printf 'smoke_phase01: PASS\n'
