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

assert_equals() {
  local expected="$1"
  local actual="$2"
  local label="$3"
  if [[ "$actual" != "$expected" ]]; then
    fail "expected $label to equal '$expected' but got '$actual'"
  fi
}

assert_files_equal() {
  local lhs="$1"
  local rhs="$2"
  cmp -s "$lhs" "$rhs" || fail "expected files to match: $lhs vs $rhs"
}

assert_word_count() {
  local expected_count="$1"
  local value="$2"
  local label="$3"
  local actual_count

  actual_count="$(awk '{ print NF }' <<<"$value")"
  if [[ "$actual_count" != "$expected_count" ]]; then
    fail "expected $label to have $expected_count fields but got $actual_count ('$value')"
  fi
}
