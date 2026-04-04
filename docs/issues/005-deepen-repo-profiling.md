# Title: feat: deepen repo profiling for sit and bark context quality

**Labels:** enhancement, p1, analysis, onboarding  
**Milestone:** Repo-Aware Intelligence  
**Depends on:** none

## Summary
Research-derived question banks and prompts are rich, but the current repo profiling layer gathers only shallow signals. This issue upgrades sit/bark context so Collie behaves more like a repo-specific maintainer.

## Problem
Too many sit/bark context fields fall back to `unknown`, reducing the quality of both philosophy generation and later triage.

### Evidence
- `src/collie/commands/sit.py`
- `src/collie/core/question_bank.py`
- `docs/research.md`

## Scope
### In scope
Enhance repo profiling to collect and summarize:
- labels and label taxonomy
- issue forms and PR templates
- discussion category forms (where relevant)
- branch protection details
- default and release/backport branch patterns
- CODEOWNERS/OWNERS coverage
- recent merged PR samples and approval counts
- stale/duplicate/security-related labels
- SECURITY.md / support policy presence
- probable test/lint/tooling signals

### Out of scope
- Execution behavior changes
- Approval authority model changes

## Proposed approach
- Expand `RepoProfile` into a richer structured profile
- Feed real profile values into sit question templates
- Reuse the profile in bark prompt context when beneficial
- Keep sparse-repo fallback behavior graceful

## Open questions
- How much API cost is acceptable during `sit`?
- Should sit have a lightweight default and an optional deep-profile mode?
- Which profile signals should be cached vs recomputed?

## Acceptance criteria
- [x] RepoProfile captures materially richer structured signals than presence checks alone
- [x] sit question templates use real repo-derived values instead of frequent `unknown` placeholders
- [x] bark prompts can reuse repo profile data where relevant
- [x] profiling still degrades gracefully on sparse or unusual repos

## Post-fix verification checklist
- [x] Add unit tests for PR template and issue form parsing
- [x] Add unit tests for label and CODEOWNERS/OWNERS detection
- [x] Add unit tests for branch protection summary extraction
- [ ] Add integration tests against representative repo shapes (small repo, monorepo, solo-maintainer repo)
- [ ] Measure and document API call/cost impact of the richer profile path

## Post-deploy validation checklist
- [ ] Run sit on at least three different sandbox/public repo types
- [ ] Confirm repo-specific question prompts now include concrete values
- [ ] Confirm generated philosophy drafts are more specific and actionable than before
- [ ] Confirm sparse repos still complete sit without hard failure
