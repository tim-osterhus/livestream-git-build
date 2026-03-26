# Livestream Git Build

This is the target repository for the livestreamed, autonomous build of a functional Git implementation built from scratch using the Millrace framework.

## Seed Prompt For This Run

The run begins from the following seed prompt:

```text
Build a functional Git implementation from scratch.

Decomposition profile: massive.

Primary objective:
Produce a local Git-compatible implementation for core repository, object, staging, commit, history, branch, checkout, diff, and tag functionality.

Must-have commands:
init
hash-object
cat-file
add
commit
log
status
diff
branch
checkout
tag

Credibility multiplier after the must-have floor:
- merge with basic non-conflicting three-way merge behavior
or
- reflog / stronger ref management

Hard constraints:
- Do not implement remote operations, HTTP transport, clone/fetch/push, or packfiles until the must-have floor is complete and validated.
- Preserve interoperability with standard Git repository and object expectations wherever required for reading and validation.
- Put implementation files for the Git tool inside `staging/` at repo root.

Focus on Git substance:
- object storage and retrieval
- index and staging semantics
- tree and commit creation
- refs, branches, HEAD, and tags
- working-tree status and diff behavior
- basic merge / ref-management credibility multiplier

Work in small, concrete steps. Prefer direct implementation and debugging over planning artifacts or harness work. If the research loop starts drifting into framework or test-harness engineering instead of Git internals, correct scope and continue.

Progress is measured by actual Git capability, host-Git interoperability, and a working credibility multiplier after the must-have floor.
```

## Completion Manifest For This Run

This run also has an explicit completion manifest. The authoritative internal copy lives in the Millrace run workspace; the manifest below is the public copy for this repository.

```json
{
  "schema_version": "1.0",
  "profile_id": "git-prelim-completion-parity-v1",
  "configured": true,
  "notes": [
    "This is the seeded completion contract for the first preliminary Millrace livestream run.",
    "The candidate entrypoint is expected at staging/run_git.sh and should behave like a git-compatible driver for the seeded command set.",
    "The blog-floor claim bundle covers the must-have local Git floor, interoperability with host git, and a basic non-conflicting merge proof.",
    "Remote operations and packfiles are intentionally out of initial required completion scope."
  ],
  "required_completion_commands": [
    {
      "id": "REPO-BASELINE-001",
      "required": true,
      "category": "repo",
      "timeout_secs": 7200,
      "command": "bash agents/tools/run_tests.sh"
    },
    {
      "id": "GIT-CORE-001",
      "required": true,
      "category": "git",
      "timeout_secs": 7200,
      "command": "bash -lc 'GIT_HARNESS_MODE=core bash agents/tools/run_git_harness.sh'"
    },
    {
      "id": "GIT-CLAIM-001",
      "required": true,
      "category": "parity",
      "timeout_secs": 10800,
      "command": "bash -lc 'GIT_CLAIM_MODE=blog_floor bash agents/tools/run_git_claim_bundle.sh'"
    }
  ],
  "optional_completion_commands": [
    {
      "id": "GIT-DIAG-MERGE-001",
      "required": false,
      "category": "parity",
      "timeout_secs": 7200,
      "command": "bash -lc 'GIT_HARNESS_MODE=merge bash agents/tools/run_git_harness.sh'"
    },
    {
      "id": "GIT-DIAG-INTEROP-001",
      "required": false,
      "category": "parity",
      "timeout_secs": 7200,
      "command": "bash -lc 'GIT_HARNESS_MODE=interop bash agents/tools/run_git_harness.sh'"
    },
    {
      "id": "GIT-STRETCH-001",
      "required": false,
      "category": "parity",
      "timeout_secs": 10800,
      "command": "bash -lc 'GIT_CLAIM_MODE=repo_stretch bash agents/tools/run_git_claim_bundle.sh'"
    }
  ]
}
```
