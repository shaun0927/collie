# Title: feat: honor branch protection, auto-merge, and merge queue during execution

**Labels:** enhancement, p1, execution, github-integration  
**Milestone:** Repo-Aware Intelligence  
**Depends on:** 001, 006

## Summary
Collie execution should not assume that direct merge is always the right path. This issue makes execution respect GitHub-native governance constraints and choose the correct execution mode.

## Problem
Collie currently weakly reflects protected branches, auto-merge, and merge queue behavior. That makes execution diverge from GitHub reality on mature repositories.

## Scope
### In scope
- Revalidate GitHub-native gates before execution
- Choose the correct execution path:
  - direct merge
  - enable auto-merge
  - enqueue into merge queue
  - hold/fail with explicit blocked reason
- Surface blocked reasons clearly in queue/state/reporting

### Out of scope
- Approval provenance storage redesign
- General repo profiling improvements

## Proposed approach
- Use the richer metadata from 006 to drive execution path selection
- Add explicit blocked/fallback outcomes when governance rules prevent immediate merge
- Keep the user-facing explanation clear when execution cannot proceed directly

## Open questions
- Should governance-aware execution be default or opt-in?
- How should Collie behave when merge queue is enabled but not writable from the current token?
- What user-facing distinction should exist between `hold`, `blocked`, and `deferred to queue`?

## Acceptance criteria
- [x] Execution distinguishes direct merge vs auto-merge vs merge-queue vs blocked outcomes
- [x] Protected-branch constraints are checked before attempting merge
- [x] Human-readable blocked reasons are surfaced in execution results
- [x] The queue/state layer preserves the chosen execution path and outcome
- [x] Training mode and authorization safeguards continue to work unchanged

## Post-fix verification checklist
- [x] Add unit tests for execution path selection under different GitHub rule combinations
- [x] Add unit tests for blocked reason generation
- [ ] Add integration tests on a repo with protected branches enabled
- [ ] Add integration tests on a repo with merge queue enabled
- [x] Add regression tests for plain unprotected repos where direct merge is valid

## Post-deploy validation checklist
- [ ] Validate approve behavior on a merge-queue-enabled sandbox repo
- [ ] Validate blocked reason reporting on a protected-branch sandbox repo
- [ ] Validate auto-merge path on a repo configured for it
- [ ] Confirm no direct merge is attempted when GitHub-native rules require another path
