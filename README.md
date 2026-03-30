# Livestream Git Build

This is the target repository for the livestreamed, autonomous build of a functional Git implementation built from scratch using the Millrace framework.

## Scope

This repository contains the published output of the first preliminary livestream run.

Current command surface:

- `init`
- `hash-object`
- `cat-file`
- `add`
- `commit`
- `log`
- `status`
- `diff`
- `branch`
- `checkout`
- `tag`
- `merge`

The implementation entrypoint is:

```bash
./run_git.sh
```

The implementation lives under:

```text
git_core/
```

Remote operations, transport, clone/fetch/push, and packfiles are intentionally out of scope for this repo state.

## Public Verification

The public harness in this repository is:

```bash
bash harness/run_git_harness.sh --candidate "$(pwd)/run_git.sh" --mode core
```

Additional harness modes:

- `interop`
- `merge`
- `blog_floor`
- `repo_stretch`

The checked-in smoke tests also target the repo-root entrypoint:

```bash
bash tests/smoke_phase01.sh
bash tests/smoke_phase02.sh
bash tests/smoke_merge_phase01.sh
bash tests/smoke_merge_phase02.sh
bash tests/smoke_merge_conflict.sh
```

## Notes

This public repo is the generated project surface only. The Millrace control workspace, audit machinery, and internal completion contracts live outside this repository and are not part of the published checkout.
