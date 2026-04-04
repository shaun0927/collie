# Title: fix: make the queue the canonical source for approval and execution

**Labels:** bug, p0, core, safety  
**Milestone:** Safety & Correctness Hardening  
**Depends on:** none

## Summary
`approve` currently rebuilds approved items from bare numbers instead of loading the actual queued recommendation payload. This issue makes the queue/state layer the canonical source for execution so human approval applies to the real recommendation, not just an item number.

## Problem
Approved items can lose their original action and type semantics before execution.

### Evidence
- `src/collie/commands/approve.py`
- Recommendation payload exists in the data model but is not restored before execution.

## Why this matters
This is the highest-risk correctness bug in the repo. Human approval should approve a specific recommendation, not merely an item number.

## Scope
### In scope
- Restore the original recommendation payload before execution
- Preserve `item_type`, `action`, `reason`, `suggested_comment`, `suggested_labels`, and `linked_pr`
- Revalidate executability before dispatching to the executor
- Update queue/state after execution without dropping context

### Out of scope
- New approval authority model
- Merge queue / auto-merge strategy changes
- Broader GitHub-native metadata expansion

## Proposed approach
- Introduce or formalize a structured recommendation state source
- Treat markdown queue rendering as presentation, not canonical execution state
- Load the real recommendation payload inside `approve`
- Ensure `hold` and `escalate` remain non-executable

## Open questions
- Where should canonical recommendation state live?
  - hidden JSON in the discussion body
  - a sibling discussion comment
  - a Collie-specific state artifact
- Should queue rendering be one-way derived output only?

## Acceptance criteria
- [x] `approve` restores the original recommendation payload from queue/state
- [x] Issue recommendations are never coerced into PR merges
- [x] `merge`, `close`, `comment`, `label`, and `link_to_pr` dispatch correctly
- [x] `hold` and `escalate` are safely skipped as non-executable
- [x] Execution results are reflected back into queue/state without losing context
- [x] Partial failures preserve per-item failure reasons

## Post-fix verification checklist
- [x] Add unit tests for action dispatch per recommendation type
- [x] Add unit tests for issue vs PR type handling
- [x] Add unit tests that hold/escalate remain non-executable
- [x] Add unit tests for preservation of comments, labels, and linked PR metadata
- [x] Add integration tests for a mixed queue containing merge/close/comment/label/link items
- [x] Add integration tests for partial success / partial failure batches
- [x] Confirm training mode still blocks execution in regression tests

## Post-deploy validation checklist
- [ ] In a sandbox repository, generate a mixed recommendation queue
- [ ] Approve multiple items with different action types
- [ ] Confirm merge recommendations merge only PRs
- [ ] Confirm close recommendations close only the intended issue/PR
- [ ] Confirm label/comment/link actions are applied correctly
- [ ] Confirm the queue reflects Executed, Failed, and Pending states accurately
