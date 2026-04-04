# Title: feat: add GitHub-native PR/review/merge metadata to Collie’s data model

**Labels:** enhancement, p1, data-model, github-integration  
**Milestone:** Repo-Aware Intelligence  
**Depends on:** 005 (nice-to-have)

## Summary
Collie’s read path needs richer GitHub-native review and mergeability signals before execution can make safe governance-aware decisions. This issue expands the data model and fetch layer only.

## Problem
Current bark analysis and execution decisions operate on incomplete metadata. Important GitHub-native signals such as draft status, review decision, author association, mergeability, and required checks are either absent or weakly modeled.

## Scope
### In scope
Add read-path/data-model support for metadata such as:
- draft status
- `reviewDecision`
- author association / trust signal inputs
- linked issues / closing references
- mergeability / merge state signals
- required checks and branch protection-relevant metadata
- auto-merge / merge-queue-related signals

### Out of scope
- Changing execution strategy
- Changing approval storage

## Proposed approach
- Extend GraphQL/REST fetches to gather richer review and merge metadata
- Extend the internal models so this data is available to bark, status, and future execution logic
- Keep this issue focused on data availability, not policy changes

## Open questions
- Which signals belong in the canonical recommendation payload vs transient runtime context?
- How should author association and trust inputs interact with philosophy-generated trust models?

## Acceptance criteria
- [x] Bark has access to draft status, review decision, and author association where available
- [x] Bark can access mergeability-related metadata and required checks signals
- [x] Linked issue and closing-reference data is available in the model layer
- [x] Status/debug output can surface at least a subset of the new metadata for inspection
- [x] No execution behavior changes are introduced in this issue

## Post-fix verification checklist
- [x] Add unit tests for new GraphQL/REST mapping logic
- [x] Add unit tests for model serialization/deserialization of new metadata
- [ ] Add integration tests against live GitHub responses where feasible
- [x] Add regression tests ensuring existing bark flows still work when fields are missing

## Post-deploy validation checklist
- [ ] Inspect bark/debug output on draft and ready-for-review PRs
- [ ] Confirm author association is surfaced for first-time and member contributors
- [ ] Confirm linked issues / closing refs appear in the runtime model
- [ ] Confirm mergeability/review metadata is available for protected-branch repos
