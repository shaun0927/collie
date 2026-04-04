# Title: fix: persist incremental bark state and detect stale recommendations across runs

**Labels:** bug, p0, performance, correctness  
**Milestone:** Safety & Correctness Hardening  
**Depends on:** 001

## Summary
Incremental bark state is effectively process-local today. This issue makes incremental mode real by persisting state and re-analyzing only changed or stale items.

## Problem
Without durable state and true delta fetches, large repos pay unnecessary analysis cost and queue correctness degrades over time.

### Evidence
- `src/collie/core/incremental.py`
- `src/collie/github/graphql.py`

## Scope
### In scope
- Persist last bark watermark and philosophy hash across runs
- Choose full scan vs incremental scan deterministically from persisted state
- Detect stale queue items caused by:
  - merged/closed items
  - new commits on PR head
  - CI state changes
  - philosophy changes
  - queue payload changes
- Re-analyze changed items when safe

### Out of scope
- New governance-aware merge execution paths
- Richer repo profiling

## Proposed approach
- Add a durable state location for bark watermarks and hashes
- Extend incremental logic to compare current remote state with prior fingerprints
- Invalidate recommendations whenever their preconditions drift

## Open questions
- Where should durable bark state live for both local CLI and GitHub Action contexts?
- Should a full scan be periodically forced even when delta state exists?

## Acceptance criteria
- [x] Bark state survives process restarts
- [x] Incremental fetch uses a real persisted watermark
- [x] Philosophy changes trigger pending recommendation invalidation
- [x] Stale recommendation detection handles closed/merged/updated items
- [x] Full scan fallback remains available and deterministic

## Post-fix verification checklist
- [x] Add unit tests for first run/full scan behavior
- [x] Add unit tests for no-change/incremental behavior
- [x] Add unit tests for philosophy hash change invalidation
- [x] Add unit tests for stale item detection due to merged/closed/new-commit/CI changes
- [x] Add integration tests for repeated bark runs on a sandbox repo

## Post-deploy validation checklist
- [ ] Run bark twice on a sandbox repo and confirm second run is incremental
- [ ] Push a new commit to an analyzed PR and confirm stale/invalidation handling
- [ ] Change philosophy and confirm affected queue items expire or recompute
- [ ] Confirm scheduled action runs reuse state correctly across invocations
