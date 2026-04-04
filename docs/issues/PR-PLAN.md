# Collie Hardening PR Plan

This document turns the hardening roadmap into reviewable PR-sized units. The goal is to land safety-critical correctness fixes first, then deepen repo intelligence, then add governance-aware execution.

## Branching and review policy
- Keep PRs narrow and reversible
- Prefer one dominant theme per PR
- Land safety/correctness PRs before feature-expansion PRs
- Preserve behavior with tests before refactors

---

## PR-01 — Queue becomes canonical execution source ✅
**Covers:** Issue 001  
**Goal:** Make `approve` execute the real queued recommendation payload.

### Likely files
- `src/collie/commands/approve.py`
- `src/collie/core/stores/queue_store.py`
- `src/collie/core/models.py`
- `tests/test_approve.py`
- `tests/test_queue_parsing.py`
- integration tests as needed

### Planned changes
- Introduce/normalize canonical recommendation restoration
- Stop synthesizing `MERGE` recommendations from raw numbers
- Preserve recommendation fields through execution

### Verification
- [x] Unit tests for mixed action dispatch
- [x] Integration tests for mixed queue execution
- [x] Regression tests for training mode blocking

### Post-deploy validation
- [ ] Run mixed recommendation execution on a sandbox repo
- [ ] Confirm merge/close/comment/label/link outcomes are all preserved end-to-end
- [ ] Confirm queue state transitions match actual GitHub-side effects

---

## PR-02 — Authenticated approval records and payload binding ✅
**Covers:** Issue 002  
**Depends on:** PR-01

### Likely files
- `src/collie/core/stores/queue_store.py`
- approval-related command/MCP wiring
- `src/collie/commands/approve.py`
- tests for approval records and authorization

### Planned changes
- Add approval provenance structure
- Bind approvals to payload hash
- Enforce authorization checks before execution

### Verification
- [x] Approval invalidation tests
- [x] Unauthorized actor tests
- [x] `approve --all` verified-approval path tests

### Post-deploy validation
- Verify maintainer approval succeeds and unauthorized edits do not trigger execution
- Verify payload mutation invalidates prior approvals
- Verify approval provenance is reconstructable after execution

---

## PR-03 — Structured analyzer output contract ✅
**Covers:** Issue 003

### Likely files
- `src/collie/core/prompts.py`
- `src/collie/core/analyzer.py`
- `src/collie/core/llm_client.py` (only if needed for structured output plumbing)
- analyzer tests

### Planned changes
- Render prompts with concrete inputs
- Introduce structured JSON outputs and validation
- Fail closed to `HOLD`

### Verification
- [x] Contract tests for T2/T3/IssueAnalyzer
- [x] Adversarial body tests
- [ ] Multi-provider compatibility smoke tests

### Post-deploy validation
- Run bark against representative live PRs/issues and inspect structured outputs
- Confirm malformed provider output downgrades to HOLD
- Confirm no provider path regresses into raw substring-based action mapping

---

## PR-04 — Persistent incremental bark state ✅
**Covers:** Issue 004  
**Depends on:** PR-01 (recommended)

### Likely files
- `src/collie/core/incremental.py`
- `src/collie/commands/bark.py`
- `src/collie/core/stores/queue_store.py` and/or new state helper
- incremental tests

### Planned changes
- Persist bark watermark/hash across runs
- Implement real delta logic
- Detect stale recommendations and invalidate appropriately

### Verification
- [x] First-run vs incremental-run tests
- [x] Philosophy-change invalidation tests
- [x] New commit / state drift stale-detection tests

### Post-deploy validation
- Run bark twice on a sandbox repo and confirm second run is incremental
- Push a new commit to an analyzed PR and confirm stale handling works
- Confirm scheduled action runs reuse state correctly across invocations

---

## PR-05 — Rich repo profiling for sit/bark ✅
**Covers:** Issue 005

### Likely files
- `src/collie/commands/sit.py`
- `src/collie/core/question_bank.py`
- possibly `src/collie/github/graphql.py` / `rest.py`
- sit/profile tests

### Planned changes
- Expand `RepoProfile`
- Parse labels, forms, branch details, ownership, and recent merge patterns
- Feed concrete values into sit templates

### Verification
- [x] Repo profiling fixture tests
- [x] Multi-repo integration checks
- [x] Graceful fallback tests for sparse repos

### Post-deploy validation
- Run sit on at least three repo shapes and confirm concrete prompt values appear
- Confirm generated philosophy drafts are more specific and actionable
- Confirm sparse repos still complete sit without hard failure

---

## PR-06 — GitHub-native review and merge metadata model ✅
**Covers:** Issue 006  
**Depends on:** PR-05 (nice-to-have)

### Likely files
- `src/collie/github/graphql.py`
- `src/collie/github/rest.py`
- `src/collie/core/models.py`
- `src/collie/commands/bark.py`
- metadata mapping tests

### Planned changes
- Fetch and model draft status, review decision, author association, linked issues, mergeability, required checks, and merge-queue-related signals
- Keep this PR read-path only

### Verification
- [x] GraphQL mapping tests
- [x] Model serialization tests
- [ ] Live metadata integration tests where possible

### Post-deploy validation
- Inspect bark/debug output on draft and ready-for-review PRs
- Confirm author association and linked issue metadata appear in runtime context
- Confirm protected-branch repos expose mergeability/review metadata correctly

---

## PR-07 — Governance-aware execution paths ✅
**Covers:** Issue 007  
**Depends on:** PR-01, PR-06

### Likely files
- `src/collie/commands/approve.py`
- `src/collie/core/executor.py`
- GitHub client layers as needed
- execution tests and sandbox integrations

### Planned changes
- Choose direct merge vs auto-merge vs merge queue vs blocked
- Surface blocked reasons in results/queue
- Respect protected-branch constraints before merge attempts

### Verification
- [x] Protected-branch tests
- [x] Merge-queue tests
- [x] Auto-merge path tests
- [x] Plain direct-merge regression tests

### Post-deploy validation
- Validate approve behavior on a merge-queue-enabled sandbox repo
- Validate blocked reason reporting on a protected-branch sandbox repo
- Validate auto-merge path where configured
- Confirm no direct merge is attempted when GitHub-native rules require another path

---

## Optional PR-08 — Docs and operator guidance sync ✅
**Covers:** follow-up docs after 001–007

### Likely files
- `README.md`
- `action.yml`
- MCP docs / examples
- `docs/e2e-report.md` or new operator docs

### Planned changes
- Update product promises to reflect final behavior
- Add active-mode operator guidance and known limitations
- Document approval provenance and governance-aware execution

### Verification
- [x] Docs review
- [x] CLI/MCP example validation
- [ ] Fresh end-to-end walkthrough on a sandbox repository

### Post-deploy validation
- Follow the published operator guide from a clean environment
- Validate README, MCP example, and Action example against actual behavior
- Confirm known limitations are documented and accurate

---

## Release guidance
- Do not market active mode as trustworthy until PR-01, PR-02, PR-03, and PR-04 are complete.
- Consider a guarded/beta release after PR-05 and PR-06.
- Treat PR-07 as the threshold for governance-aware execution readiness on mature repositories.
