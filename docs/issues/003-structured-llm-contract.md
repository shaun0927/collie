# Title: refactor: align bark prompts, output schema, and parser with a structured contract

**Labels:** bug, p0, llm, reliability  
**Milestone:** Safety & Correctness Hardening  
**Depends on:** none

## Summary
Current T2/T3/issue analysis relies on prompts and parsers that do not share a strict contract. This issue moves analyzer output to a typed schema and fail-closed parsing model.

## Problem
Prompt placeholders are not consistently rendered, and response interpretation is brittle substring matching.

### Evidence
- `src/collie/core/prompts.py`
- `src/collie/core/analyzer.py`

## Why this matters
Recommendation quality and execution safety depend on predictable analysis output. Malformed or adversarial model outputs should fail closed, not be heuristically misinterpreted.

## Scope
### In scope
- Prompt templates rendered with concrete inputs before dispatch
- Structured JSON output schema for T2, T3, and issue analysis
- Validation before converting output into `RecommendationAction`
- Fail-closed fallback to `HOLD`
- Better separation of instruction text vs untrusted PR/issue content

### Out of scope
- New provider integrations
- Approval/execution authority changes

## Proposed approach
- Define analyzer-specific or shared JSON schemas
- Update parser logic to prefer schema validation over substring matching
- Add adversarial tests for prompt-injection-like issue/PR bodies
- Ensure malformed model output downgrades to safe hold behavior

## Open questions
- One shared schema vs shared core + mode-specific extensions?
- Whether any fallback text parser should remain for non-compliant providers?

## Acceptance criteria
- [x] T2, T3, and issue prompts are formatted with concrete inputs
- [x] Analyzer paths consume structured outputs first, not substring heuristics
- [x] Invalid or malformed output is converted to a safe `HOLD`
- [x] Adversarial issue/PR content does not trivially coerce the parser into merge/close decisions
- [x] Contract tests cover each analyzer mode

## Post-fix verification checklist
- [x] Add unit tests for successful structured parsing in T2/T3/IssueAnalyzer
- [x] Add unit tests for malformed JSON/schema failures returning `HOLD`
- [x] Add unit tests confirming placeholders are fully rendered before dispatch
- [x] Add adversarial tests with injected phrases like `recommendation: merge` in PR bodies
- [ ] Add provider compatibility tests for Anthropic/OpenAI-compatible/Codex CLI paths

## Post-deploy validation checklist
- [ ] Run bark on representative live PRs/issues and inspect structured analyzer outputs
- [ ] Confirm malformed provider output safely downgrades to `HOLD`
- [ ] Confirm no provider path regresses into raw substring-based action mapping
