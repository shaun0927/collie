# Post-Deploy Validation Runbook

This runbook captures the recommended post-deploy validation sequence for Collie after the hardening work through PR-08.

## Validation tiers

### Tier 0 — deployment integrity
Purpose: confirm that the intended code is what is actually deployed.

- Verify local HEAD matches `origin/main`
- Run `ruff check src tests`
- Run `pytest -q`
- Build distributables with `python -m build --sdist --wheel`
- Run `collie --help`

### Tier 1 — safe sandbox workflow validation
Purpose: verify the default training/active/approve/bark flows on a sandbox repository.

Recommended repository profile:
- Discussions enabled
- a few open PRs/issues
- maintainer token available
- no destructive production consequences

Commands:
```bash
collie status <owner/repo>
collie sit <owner/repo>
collie bark <owner/repo> --cost-cap 1
collie approve <owner/repo> <numbers...>
collie approve <owner/repo> --all
```

Expected outcomes:
- `status` returns current mode and queue counts
- `bark` refreshes recommendations and queue state
- explicit `approve` records verified approvals and executes the intended recommendation type
- `approve --all` executes verified approvals only

### Tier 2 — protected-branch / blocked-path validation
Purpose: prove that Collie does **not** force direct merge where GitHub-native governance should block it.

Required repo setup:
- protected default branch
- required checks and/or required review rules enabled
- at least one PR in a draft or blocked state

Validation scenarios:
1. **Draft PR**
   - Recommendation action: merge
   - Expected result: blocked
   - Expected message: `Blocked: draft PR`
2. **Changes requested**
   - Expected result: blocked
   - Expected message: `Blocked: changes requested`
3. **Merge conflict**
   - Expected result: blocked
   - Expected message: `Blocked: merge conflict`
4. **Failing checks**
   - Expected result: blocked
   - Expected message: `Blocked: required checks failing`

CLI verification:
```bash
collie approve <owner/repo> <pr-number>
```

Queue verification:
- failed entries show a blocked reason
- execution path is preserved as `blocked`

### Tier 3 — auto-merge validation
Purpose: prove pending-check PRs choose the auto-merge path rather than direct merge when supported.

Required repo setup:
- auto-merge enabled on the repository
- PR with pending/expected checks
- token allowed to enable auto-merge

Expected result:
- execution succeeds without direct merge
- message indicates `Auto-merge enabled`
- execution path is preserved as `auto_merge`

### Tier 4 — merge queue validation
Purpose: prove merge-queue-required situations take the queue path or clearly block.

Required repo setup:
- merge queue configured on the default branch
- PR eligible for queueing
- token allowed to enqueue

Expected result:
- success path: `Enqueued in merge queue`
- fallback path: `Blocked: merge queue required`
- execution path preserved as `merge_queue` or `blocked`

## What was validated in this session

### Completed
- deployment integrity checks
- sandbox workflow validation against `shaun0927/collie-test-sandbox`
- live integration tests:
  - `tests/test_issue7_verification.py`
  - `tests/test_issue8_verification.py`
- CLI runtime checks:
  - `collie status shaun0927/collie`
  - `collie status shaun0927/collie-test-sandbox`
  - `collie bark shaun0927/collie-test-sandbox --cost-cap 1`
  - `collie approve shaun0927/collie-test-sandbox --all`

### Not completed
- protected-branch live blocked-path validation
- live auto-merge path validation
- live merge queue enqueue validation

## Why the remaining checks were not completed here

During this validation pass, the accessible sandbox repository `shaun0927/collie-test-sandbox` reported `Branch not protected`, so it could not exercise the protected-branch / merge-queue / auto-merge governance scenarios directly.

Those scenarios still need a purpose-built sandbox repository with the required GitHub settings enabled.

## Recommended next repositories / setups

Create or reuse a dedicated validation sandbox for each of the following:
- `collie-protected-branch-sandbox`
- `collie-auto-merge-sandbox`
- `collie-merge-queue-sandbox`

Each should contain:
- Discussions enabled
- at least one safe test PR
- maintainer-owned token available for automation testing
- no production data or deployment side effects
