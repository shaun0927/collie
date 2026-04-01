# Collie v0.1.0 — E2E Test Report

**Date:** 2026-04-01
**Test repo:** shaun0927/fastapi (fork of tiangolo/fastapi)
**Data source:** tiangolo/fastapi (154 PRs, 22 issues)

## Test Results

### Scenario A: sit -> bark Pipeline

| Step | Result | Details |
|------|--------|---------|
| RepoAnalyzer | PASS | Detected CONTRIBUTING.md, CI workflows |
| Philosophy save | PASS | Created Discussion in "General" category |
| Philosophy load | PASS | Roundtrip: 2 hard rules, mode=training |
| bark T1 scan | PASS | 154 PRs analyzed in <5s |

### T1 Analysis Results (154 PRs)

| Action | Count | % |
|--------|-------|---|
| Merge | 3 | 2% |
| Close (CI failed) | 33 | 21% |
| Hold (needs T2) | 118 | 77% |

### Merge Recommendation Verification

T1 merge recommendations (3 PRs) — docs-only PRs with CI pass + reviews.
These are conservative recommendations consistent with the "zero false merge" policy.

**Sampling verdict:** 3/3 merge recommendations appear reasonable (docs-only changes).

### Bugs Found & Fixed

| Bug | Location | Fix |
|-----|----------|-----|
| `get_repo_content` fails on directories | `rest.py:146` | Handle list response for directory listings |
| GraphQL URL trailing slash | `graphql.py:101` | Changed base_url to `api.github.com`, post to `/graphql` |
| `statusCheckRollup` null | `analyzer.py:95,190` | Add None check before `.get()` |
| `list_discussions` missing | `graphql.py` | Added method with pagination |
| `get_repository_id` missing | `graphql.py` | Added query method |
| Method name mismatches | `graphql.py` | Added aliases: `list_discussion_categories`, `update_discussion_body` |
| `create_discussion` kwarg mismatch | `philosophy_store.py:30` | `repo_id=` -> `repository_id=` |
| Category creation not supported by API | `philosophy_store.py:85` | Fallback to "General" category |
| `_find_discussion` category filter too strict | `philosophy_store.py:79` | Search all categories by title |

**Total bugs found:** 9
**All fixed and tests passing:** 182/182

## Performance

| Metric | Value |
|--------|-------|
| RepoAnalyzer | ~3s |
| GraphQL fetch (154 PRs + 22 issues) | ~2s |
| T1 scan (154 PRs) | <0.1s |
| Philosophy save/load roundtrip | ~1s |
| LLM cost (T1 only) | $0.00 |

## Infrastructure Verified

- [x] GitHub PAT authentication (via env)
- [x] GraphQL pagination (100 items per page)
- [x] REST API write operations (Discussion create)
- [x] Discussion as storage backend
- [x] Philosophy markdown serialization roundtrip
- [x] T1 rule engine (CI failed -> reject, docs-only -> merge)

## Not Yet Tested (Requires LLM API key)

- [ ] T2 Summarizer (LLM-based)
- [ ] T3 Deep Reviewer (LLM-based)
- [ ] Issue Analyzer (LLM-based)
- [ ] Queue Living Document update
- [ ] Approve + Execute pipeline
- [ ] Micro-update on rejection
- [ ] Unleash mode transition
- [ ] Incremental (delta) processing
- [ ] GitHub Action cron mode

## Conclusion

Collie v0.1.0 E2E testing on real fastapi data (154 PRs) confirms:
1. **Pipeline works end-to-end**: sit -> bark -> analysis produces reasonable results
2. **Conservative merge policy enforced**: Only 3 merge recommendations (all docs-only)
3. **9 integration bugs found and fixed** — all in API layer/store layer mismatches
4. **182 unit tests remain green** after all fixes
5. **T1 analysis is fast and free** — 154 PRs in <5s, $0 cost

Next steps: Test with `ANTHROPIC_API_KEY` for T2/T3 analysis, and test approve/execute on fork.
