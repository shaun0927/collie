# Title: epic: harden Collie for trustworthy active-mode triage and execution

**Labels:** epic, safety, roadmap  
**Milestone:** Safety & Correctness Hardening  
**Depends on:** none

## Summary
Collie has strong product direction, but active mode is not yet trustworthy enough for production-grade repository triage and execution. This epic tracks the work needed to make recommendation generation, approval, and execution consistent, auditable, and aligned with GitHub-native governance.

## Goals
- Make the queue and execution pipeline semantically correct
- Prevent unauthorized or ambiguous approvals from triggering execution
- Harden LLM contracts and parsing behavior
- Make incremental bark runs real and efficient
- Improve repo-specific intelligence quality
- Align execution with protected branches, merge queue, forms, and projects metadata

## Child issues
- [ ] 001 — Make the queue the canonical source for approval + execution
- [ ] 002 — Replace checkbox-only approvals with authenticated GitHub approvals
- [ ] 003 — Align bark prompts, output schema, and parser
- [ ] 004 — Persist incremental bark state and detect stale recommendations
- [ ] 005 — Deepen repo profiling for sit/bark context
- [ ] 006 — Add GitHub-native PR/review/merge metadata to Collie’s data model
- [ ] 007 — Honor branch protection, auto-merge, and merge queue during execution

## Epic completion checklist
- [ ] Recommendation payload is preserved end-to-end from bark to approve to execute
- [ ] Approval provenance is recorded and validated
- [ ] LLM outputs are schema-validated and fail closed on malformed responses
- [ ] Incremental bark uses persisted state and re-analyzes only changed items
- [ ] Repo profiling produces materially fewer `unknown` fields in sit/bark context
- [ ] The data model exposes GitHub-native review and mergeability signals
- [ ] Execution respects protected branches, auto-merge, and merge queue behavior
- [ ] CLI, MCP, and GitHub Action docs reflect the final behavior
- [ ] End-to-end validation passes on at least one sandbox repository

## Post-deploy validation checklist
- [ ] Run a full `sit -> bark -> approve -> execute` flow on a sandbox repo
- [ ] Confirm training mode still blocks execution
- [ ] Confirm active mode only executes verified approvals
- [ ] Confirm mixed recommendation types (merge/close/label/comment/link) all behave correctly
- [ ] Confirm auditability: actor, approved payload, and execution result can be reconstructed
