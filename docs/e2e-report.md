# Collie v0.1.0 — E2E Test Report

**Date:** 2026-04-01
**Test repo:** shaun0927/fastapi (fork of tiangolo/fastapi)
**Data source:** tiangolo/fastapi (154 PRs, 22 issues = 176 items)

## Test Results Summary

| Test | Result | Details |
|------|--------|---------|
| RepoAnalyzer (sit) | **PASS** | Detected CONTRIBUTING.md, CI workflows |
| Philosophy save/load | **PASS** | Discussion roundtrip, 2 hard rules |
| GraphQL bulk fetch | **PASS** | 176 items in ~2s with pagination |
| T1 Scanner (154 PRs) | **PASS** | 3 merge, 33 close, 118 hold |
| T2 Summarizer (Codex OAuth) | **PASS** | Dependabot major bump → hold |
| Issue Analyzer (Codex OAuth) | **PASS** | 3 issues classified correctly |
| bark full pipeline | **PASS** | 176 items → 165 pending recommendations |
| Discussion Queue creation | **PASS** | [shaun0927/fastapi#2](https://github.com/shaun0927/fastapi/discussions/2) |
| Codex OAuth auto-detect | **PASS** | No API key → CodexLLMClient |

## Detailed Results

### Scenario A: sit → bark Pipeline

| Step | Result | Time |
|------|--------|------|
| RepoAnalyzer | PASS | ~3s |
| Philosophy save | PASS | ~1s |
| Philosophy load | PASS | ~1s |
| bark T1 scan (176 items) | PASS | <1s |
| Queue Discussion create | PASS | ~1s |
| **Total pipeline** | **PASS** | **~6s** |

### T1 Analysis Results (154 PRs + 22 Issues)

| Action | Count | % | Notes |
|--------|-------|---|-------|
| Merge | 3 | 2% | Docs-only PRs with CI pass + reviews |
| Close | 33 | 19% | CI failed → hard rule rejection |
| Hold | 140 | 79% | Needs T2/T3 analysis |
| **Total** | **176** | **100%** | |

### T2 Analysis (Codex OAuth)

- **PR #15267** (Dependabot: fastmcp 2.14.5 → 3.2.0)
  - Result: **hold** — "crosses a major version boundary, backward-compatibility risk"
  - Verdict: **Correct** — philosophy's backward compat preference reflected

### Issue Analysis (Codex OAuth)

- **Issue #13056** → label (BUG, HIGH confidence)
- **Issue #10180** → label (BUG, MEDIUM confidence)
- **Issue #13399** → label (BUG, MEDIUM confidence)
- Verdict: **All correct** — properly classified bug reports

### Discussion Queue

- Created at: https://github.com/shaun0927/fastapi/discussions/2
- Format: Living Document with checkboxes
- 165 pending items with `- [ ]` checkboxes
- Mode: training (execution blocked)

## LLM Backend Verification

| Backend | Status | Notes |
|---------|--------|-------|
| Anthropic API (ANTHROPIC_API_KEY) | Supported | Direct API calls |
| Codex OAuth (codex CLI) | **Verified** | T2 + Issue analysis working |
| No LLM | **Verified** | T1-only mode, $0 cost |
| Auto-detect | **Verified** | Correctly falls back to Codex |

## Bugs Found & Fixed (Total: 9)

| # | Bug | Location | Fix |
|---|-----|----------|-----|
| 1 | `get_repo_content` fails on directories | `rest.py:146` | Handle list response |
| 2 | GraphQL URL trailing slash | `graphql.py:101` | Fix base_url + endpoint |
| 3 | `statusCheckRollup` null | `analyzer.py:95,190` | Add None check |
| 4 | `list_discussions` missing | `graphql.py` | Added method |
| 5 | `get_repository_id` missing | `graphql.py` | Added method |
| 6 | Method name aliases missing | `graphql.py` | Added aliases |
| 7 | `create_discussion` kwarg mismatch | `philosophy_store.py` | `repo_id` → `repository_id` |
| 8 | Category creation not supported | `philosophy_store.py` | Fallback to "General" |
| 9 | `_find_discussion` filter too strict | `philosophy_store.py` | Search all categories |

## Performance

| Metric | Value |
|--------|-------|
| GraphQL fetch (176 items) | ~2s |
| T1 scan (176 items) | <0.1s |
| T2 analysis (1 PR via Codex) | ~15s |
| Issue analysis (1 issue via Codex) | ~20s |
| Philosophy save/load | ~1s each |
| Queue Discussion create | ~1s |
| LLM cost (T1 only, 176 items) | **$0.00** |

## Not Yet Tested

- [ ] T3 Deep Reviewer (full diff analysis)
- [ ] approve + execute (merge/close on fork)
- [ ] Micro-update on rejection
- [ ] Unleash mode transition + execution
- [ ] Incremental (delta) processing
- [ ] GitHub Action cron mode
- [ ] Checkbox approval detection

## Conclusion

Collie v0.1.0 E2E testing on tiangolo/fastapi (176 items) confirms:

1. **Full pipeline works**: sit → bark → Discussion Queue creation
2. **Conservative merge enforced**: Only 3 merge recommendations (all docs-only)
3. **Codex OAuth works**: T2/Issue analysis without API key
4. **Discussion storage works**: Philosophy + Queue as living documents
5. **9 integration bugs found and fixed**
6. **182 unit tests remain green**
7. **T1 is fast and free**: 176 items in <1s, $0

### Verdict: **v0.1.0 is functional for core workflow (sit → bark → queue)**
