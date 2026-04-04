# Merge Queue Validation Setup

This document explains how to complete the remaining live validation scenario for Collie's merge-queue execution path.

## Current status

A dedicated organization-owned sandbox now exists:

- `jh-ohmee/collie-merge-queue-sandbox`

Using that repository, the **blocked** merge-queue-required path was validated live.

What is still pending is the **successful enqueue path** (`Enqueued in merge queue`), which requires a repository configuration and token combination that can actually place a PR into the queue.

## Recommended sandbox requirements

Create or prepare a dedicated repository with these properties:

- repository owned by an organization that supports merge queue for the target plan
- admin access available to the validation operator
- Discussions enabled
- at least one safe test branch with a mergeable PR
- branch rules or rulesets configured so that the default branch **requires merge queue**
- required status checks configured for that branch

## Suggested repository name

- `jh-ohmee/collie-merge-queue-sandbox` (existing)

## One-time repository setup checklist

- [ ] Create repository
- [ ] Enable Discussions
- [ ] Enable pull requests and standard merge methods as needed by your ruleset
- [ ] Configure required status checks on the default branch
- [ ] Configure a repository ruleset or branch protection rule that **requires merge queue**
- [ ] Ensure merge-group workflows/status checks are configured if your queue setup requires them

## Validation branches and PRs

Prepare at least two branches:

- `validation/merge-queue-happy-path`
- `validation/merge-queue-blocked-path`

Open PRs from each branch into `main`.

## Validation scenario A — queue path succeeds

Goal: confirm Collie chooses `merge_queue` when queueing is required and supported.

### Preconditions
- merge queue is required on the target branch
- PR is mergeable
- required checks are passing or in the expected queue-ready state
- token used by Collie has permission to enqueue

### Expected result
- `collie approve <repo> <pr-number>` does **not** direct-merge
- execution result message includes `Enqueued in merge queue`
- execution path is recorded as `merge_queue`

### Suggested checks
- [ ] CLI output shows a successful queue-enqueue result
- [ ] queue discussion/state preserves `execution_path = merge_queue`
- [ ] GitHub UI shows the PR in the merge queue

## Validation scenario B — queue required but enqueue unavailable

Goal: confirm Collie fails clearly when merge queue is required but cannot be used.

### Preconditions
Any of the following is sufficient:
- token lacks permission to enqueue
- queue support is not actually available for the repo/branch setup
- queueing endpoint or required support is missing

### Expected result
- no direct merge is attempted
- execution result is blocked/failure
- message includes `Blocked: merge queue required`
- execution path is recorded as `blocked`

### Suggested checks
- [ ] CLI output surfaces a blocked result
- [ ] queue discussion/state preserves `execution_path = blocked`
- [ ] PR remains open and unmerged

## End-to-end command sequence

```bash
# Confirm repo status and mode
collie status <owner/repo>

# Refresh recommendations
collie bark <owner/repo> --cost-cap 1

# Approve a merge recommendation that targets the merge queue path
collie approve <owner/repo> <pr-number>
```

## Evidence to capture

For each run, save:
- CLI output
- queue discussion link or body snapshot
- PR URL
- branch ruleset screenshot or settings export if available

## Reference docs

- GitHub Docs — Using a merge queue: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/using-a-merge-queue
- GitHub Docs — Available rules for rulesets (`Require merge queue`): https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
