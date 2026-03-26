#!/usr/bin/env bash

fail() {
  printf 'ASSERTION FAILED: %s\n' "$*" >&2
  exit 1
}

assert_file_exists() {
  local path="$1"
  [ -f "$path" ] || fail "expected file to exist: $path"
}

assert_dir_exists() {
  local path="$1"
  [ -d "$path" ] || fail "expected directory to exist: $path"
}

assert_match() {
  local value="$1"
  local pattern="$2"
  local label="$3"
  if [[ ! "$value" =~ $pattern ]]; then
    fail "expected $label to match pattern '$pattern' but got '$value'"
  fi
}

assert_files_equal() {
  local lhs="$1"
  local rhs="$2"
  cmp -s "$lhs" "$rhs" || fail "expected files to match: $lhs vs $rhs"
}
