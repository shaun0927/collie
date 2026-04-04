# Title: security: replace checkbox-only approvals with authenticated GitHub approvals

**Labels:** security, p0, safety, authz  
**Milestone:** Safety & Correctness Hardening  
**Depends on:** 001

## Summary
Approval is currently inferred from editable discussion markdown checkboxes. This issue adds approver provenance, payload binding, and authorization verification so execution authority is tied to real GitHub actors.

## Problem
A checked box is not a trustworthy authorization primitive for repository-changing actions.

### Evidence
- `src/collie/core/stores/queue_store.py`
- `README.md` queue approval model

## Why this matters
Approval must be attributable to a real GitHub actor and bound to a specific recommendation payload. Without that, markdown edits can effectively authorize execution.

## Scope
### In scope
- Verified approval records with approver identity, timestamp, payload hash, and approval source
- Role/capability verification for approvers
- Automatic invalidation when recommendation payload changes
- `approve --all` consuming verified approvals only

### Out of scope
- Queue payload correctness itself (covered by 001)
- Merge strategy / governance execution paths

## Proposed approach
- Introduce a structured approval record
- Treat checkbox UX as a convenience layer only
- Bind approvals to recommendation payload hashes
- Enforce actor-level authorization before execution

## Open questions
- Minimum acceptable authority model: collaborator vs maintainer vs team/code-owner-aware?
- Best approval source: structured comments/commands, dedicated approval block, or external state artifact?
- How much audit history should remain GitHub-visible?

## Acceptance criteria
- [x] Approval records include approver identity and approved payload hash
- [x] Unauthorized actors cannot trigger execution via raw markdown edits
- [x] Payload changes automatically invalidate prior approvals
- [x] `approve --all` consumes verified approvals only
- [x] Approval provenance is inspectable for debugging and audit purposes

## Post-fix verification checklist
- [x] Add unit tests for approval record serialization/deserialization
- [x] Add unit tests for payload hash mismatch invalidation
- [x] Add unit tests for unauthorized approver rejection
- [x] Add integration tests for multiple approvals on the same queue item
- [x] Add integration tests for approval invalidation after queue mutation
- [x] Add regression tests for training vs active mode behavior

## Post-deploy validation checklist
- [ ] Verify maintainer approval succeeds in a sandbox repo
- [ ] Verify unauthorized or non-maintainer edits do not trigger execution
- [ ] Verify mutated recommendation payload invalidates old approvals
- [ ] Verify approval audit info can be reconstructed after execution
