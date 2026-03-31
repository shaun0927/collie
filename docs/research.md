# Collie Phase 0 Research: Exemplary Repository Review Processes

> Research date: 2026-03-31
> Repos analyzed: kubernetes/kubernetes, facebook/react, django/django, tiangolo/fastapi, vercel/next.js

---

## 1. Per-Repo Review Process Summaries

### kubernetes/kubernetes

**Scale**: Massive monorepo (~100k+ files). Organized by Special Interest Groups (SIGs).

**Contributing process**:
- CLA (Contributor License Agreement) required before any PR is considered
- PRs must be labeled by kind (`/kind bug`, `/kind feature`, `/kind cleanup`, `/kind api-change`, `/kind deprecation`, `/kind documentation`)
- PRs targeting a release must be labeled for release milestone
- Tests must be added or verified for every PR (`/sig testing` docs)
- PRs need `/lgtm` (looks good to me) and `/approve` comments from authorized reviewers — these are bot-enforced via prow/tide
- Bot (`k8s-ci-robot`) automatically assigns reviewers based on OWNERS files
- Unfinished PRs must be marked with `[WIP]` prefix or `do-not-merge/work-in-progress` label

**PR template fields**:
- Type of PR (kind label required)
- What this PR does / why we need it
- Which issue(s) this PR fixes
- Special notes for reviewer
- Does this PR introduce a user-facing change? (release notes)
- Additional documentation

**Label taxonomy** (representative sample):
- `kind/bug`, `kind/feature`, `kind/cleanup`, `kind/design`, `kind/documentation`, `kind/api-change`, `kind/deprecation`, `kind/failing-test`, `kind/flake`, `kind/regression`
- `priority/critical-urgent`, `priority/important-soon`, `priority/important-longterm`, `priority/backlog`
- `area/*` (hundreds of area labels by component)
- `sig/*` (SIG ownership labels)
- `do-not-merge/hold`, `do-not-merge/work-in-progress`, `do-not-merge/needs-rebase`
- `lgtm`, `approved`

**Merge criteria**:
- `/lgtm` from at least one reviewer in OWNERS file
- `/approve` from an approver in OWNERS file
- All required CI checks passing (prow jobs)
- No `do-not-merge/*` labels present
- CLA signed

**Common rejection reasons**:
- Missing kind label
- No associated issue/ticket
- Missing release notes for user-facing changes
- Tests not included
- CLA not signed
- PR targets wrong branch for the change type

**PR size patterns**: Enormous variance — from 1-line fixes to thousands of lines. Bot labels PRs as `size/XS`, `size/S`, `size/M`, `size/L`, `size/XL`, `size/XXL`.

---

### facebook/react

**Scale**: Medium-large monorepo. Maintained primarily by Meta/React Core Team.

**Contributing process**:
- CLA required (tracked via `CLA Signed` label)
- Fork repo, create branch from `main`
- Run `yarn` in root before starting
- Tests required for bug fixes and new code (`yarn test`)
- Prettier formatting enforced (`yarn prettier`)
- ESLint linting enforced (`yarn lint`)
- Flow type checks required (`yarn flow`)
- PR template requires: Summary of motivation and How you tested the change

**PR template fields**:
- Summary (motivation / problem solved)
- How did you test this change? (empty = likely closed)

**Label taxonomy**:
- `Type: Bug`, `Type: Enhancement`, `Type: Feature Request`, `Type: Breaking Change`, `Type: Regression`, `Type: Discussion`, `Type: Big Picture`, `Type: Umbrella`, `Type: Release`, `Type: Needs Investigation`
- `Component: Reconciler`, `Component: Hooks`, `Component: Scheduler`, `Component: Server Rendering`, `Component: Suspense`, `Component: Concurrent Features`, `Component: DOM`, `Component: Developer Tools`, `Component: React Compiler`, `Component: Fast Refresh`, `Component: ESLint Rules`
- `Resolution: Duplicate`, `Resolution: Invalid`, `Resolution: Wontfix`, `Resolution: Needs More Information`, `Resolution: Support Redirect`, `Resolution: Unsolved`
- `Difficulty: starter`, `Difficulty: medium`, `Difficulty: challenging`
- `Status: Unconfirmed`, `Status: New`, `Status: Reverted`
- `Needs Browser Testing` (manual testing before merge)
- `CLA Signed`, `React Core Team`, `good first issue`

**Merge criteria**:
- At least 1 reviewer approval (often from React Core Team member)
- CLA Signed
- All CI checks pass (test suite, lint, Flow types, Prettier)
- Test coverage for new behavior

**Common rejection reasons**:
- Empty "How did you test this change?" field
- No CLA
- Feature requests that don't align with React's direction
- Missing tests
- Formatting/lint failures

**PR size patterns** (from real merged PRs):
- Documentation fixes: 3–20 lines changed
- Bug fixes: 3–100 lines changed, 1–5 files
- Features: 70–500 lines, 3–10 files
- Large features: 500–1636 lines, 10–30 files
- Reviews typically 1 approver for most PRs; core team self-merges are common

---

### django/django

**Scale**: Large mature Python web framework. Uses Trac issue tracker in addition to GitHub.

**Contributing process**:
- **Non-trivial PRs without a Trac ticket will be closed** — this is enforced strictly
- `no ticket` label is auto-applied if no Trac reference found in PR title
- Contributors must file a ticket on Trac (`code.djangoproject.com`) first for any non-trivial change
- PR title should reference ticket: `Fixed #NNNNN -- Description` or `Refs #NNNNN -- Description`
- Bot posts first-contribution welcome and checklist
- Django has an AI contribution disclosure policy — contributors must disclose AI tool usage
- Reviews are iterative with multiple rounds of comments
- Djangonauts program for mentored first-time contributors (`Djangonauts :rocket:` label)
- 2+ reviewer approvals typical for non-trivial changes

**PR template**: Minimalist — no formal template found, but title convention is strictly enforced.

**Label taxonomy**:
- `bug`, `enhancement`, `duplicate`, `invalid`, `question`, `wontfix`
- `no ticket` (auto-applied, often leads to closure)
- `benchmark`, `selenium`, `screenshots`, `coverage`, `python-matrix`, `geodjango`
- `Djangonauts :rocket:`, `reminder`
- Conference labels: `DjangoCon`, `DjangoCon Europe`

**Merge criteria**:
- Trac ticket exists and is referenced in title
- At least 1 member (MEMBER association) approval
- Tests included for code changes
- Documentation updated if needed
- Passes CI (test matrix across Python versions, DBs)
- Code formatted with Black

**Common rejection reasons**:
- No Trac ticket (`no ticket` label → closure)
- PR opened without community discussion for significant changes
- Missing tests
- Documentation not updated

**PR size patterns**: Highly variable — documentation and small fixes are 1–5 lines; substantive fixes are 20–200 lines. Review rounds are extensive (5–10 review comments back-and-forth).

---

### tiangolo/fastapi

**Scale**: Medium Python framework. Primarily maintained by single author (tiangolo).

**Contributing process**:
- Contributing guide defers entirely to documentation site (fastapi.tiangolo.com/contributing/)
- No formal PR template found
- Translation PRs are a major category (`lang-*` labels) — managed separately
- Most code PRs are reviewed by tiangolo personally
- `community-feedback` label used to gather community input before decision
- `awaiting-review` and `approved-2` labels track review pipeline stages
- Dependency updates largely automated via Dependabot
- `maybe-ai` label applied to suspected AI-generated PRs
- `reviewed` label marks completed first-pass review
- `investigate` label for issues needing deeper analysis

**Label taxonomy**:
- `bug`, `feature`, `duplicate`, `invalid`, `question`, `wontfix`, `help wanted`, `good first issue`
- `docs`, `lang-*` (50+ language translation labels)
- `dependencies`, `github_actions`, `python`
- `community-feedback`, `awaiting-review`, `approved-2`, `reviewed`, `confirmed`, `answered`
- `hacktoberfest-accepted`, `maybe-ai`, `investigate`, `info missing`, `question-migrate`
- `internal`

**Merge criteria**:
- Author review/approval (tiangolo is primary gatekeeper)
- For translation PRs: community review + tiangolo merge
- Dependency updates: automated, merged without review
- `approved-2` label indicates ready for final merge

**Common rejection reasons**:
- Suspected AI-generated content without disclosure (`maybe-ai` label)
- Duplicate PRs (multiple reopened translation PRs observed)
- Missing information (`info missing`)
- Breaking API changes without discussion

**PR size patterns**:
- Dependency bumps: 3–8 lines, 1 file
- Doc fixes: 2–20 lines
- Translation updates: 522–846 lines, ~98 files (automated batch)
- Code features: 15–755 lines

---

### vercel/next.js

**Scale**: Very large. Active daily development by Vercel team + community. Uses linear.app for issue tracking.

**Contributing process**:
- Watch video walkthrough recommended before contributing
- Search existing PRs/issues before opening
- Separate docs for different areas: core, turbopack, docs, testing, linting
- PRs must have detailed descriptions (dedicated `pull-request-descriptions.md` guide)
- `CI approved` label required for fork PRs before CI runs (security gate)
- Triaging docs exist as a formal process (`triaging.md`)
- `linear: next`, `linear: turbopack`, `linear: docs` labels indicate confirmed issues tracked in Linear
- Team labels: `created-by: Next.js team`, `created-by: Turbopack team`, `created-by: Next.js Docs team`, `created-by: Next.js DevEx team`
- Backport process: `Backport` label marks PRs ready for stable version backport

**PR template**: No single template found — PR descriptions guide is separate doc.

**Label taxonomy**:
- Type/feature labels: `bug`, `type: next`, `Turbopack`, `Middleware`, `Image (next/image)`, `Linking and Navigating`, `TypeScript`, `Runtime`, `Pages Router`, `Metadata`, `Font (next/font)`, `Lazy Loading`, `Script (next/script)`, `Internationalization (i18n)`, `SWC`, `Webpack`, `Testing`, `Performance`, `Documentation`, `Cache Components`, `Module Resolution`, `Instrumentation`, `Parallel & Intercepting Routes`, `Markdown (MDX)`
- Triage labels: `please add a complete reproduction`, `please verify canary`, `please simplify reproduction`, `invalid link`, `stale`, `locked`, `resolved`
- Process labels: `CI approved`, `CI Bypass Graphite Optimization`, `Backport`, `run-react-18-tests`, `created-by: *` team labels, `linear: *`
- `good first issue`, `Upstream`, `examples`, `create-next-app`

**Merge criteria**:
- Team member approval (Next.js/Turbopack/Docs team)
- CI must pass (and must be explicitly approved for fork PRs)
- Tests added for behavioral changes (`tests` label on test-inclusive PRs)
- Backport label added for fixes targeting stable release

**Common rejection reasons**:
- Missing reproduction link (auto-closed via `invalid link`)
- Issue needs canary verification first
- Upstream dependency issue (not Next.js's responsibility)
- PR superseded by backport or team-authored version

**PR size patterns**:
- CI/config: 2–5 lines
- Bug fixes: 16–93 lines, 4–20 files
- Features: 293–1636 lines, 11–82 files
- Documentation: 1–1095 lines
- React sync upgrades: 1636 lines, 82 files (automated)

---

## 2. Cross-Repo Common Patterns

### Universal merge criteria (all 5 repos)
1. **CI must pass** — every repo has automated CI and expects it to pass before merge
2. **At least 1 reviewer approval** — no repo merges unreviewed (except automated bots/maintainer self-merge)
3. **CLA or contributor agreement** — kubernetes (CLA), react (CLA), django (implicit CoC), fastapi (implicit), next.js (implicit)
4. **Tests for behavioral changes** — all 5 require tests for non-trivial code changes
5. **Linting/formatting** — all 5 enforce code style (Go fmt, Prettier, Black, Ruff, ESLint)

### Common rejection patterns (4/5 repos)
- **Missing tests** — almost universal rejection reason
- **No linked issue/ticket** — kubernetes (kind label), django (Trac ticket), next.js (linear), react (issue mention)
- **Insufficient PR description** — react explicitly closes PRs with empty test description
- **Breaking changes without prior discussion** — all large repos expect design discussion first
- **Duplicate PRs** — all repos have duplicate resolution labels/processes

### Review patterns
- **Single reviewer sufficient for small fixes** — docs, typos, minor bug fixes get 1 reviewer across all repos
- **2+ reviewers for features** — django consistently shows 2+ approvals for features; react core team often cross-reviews
- **Bot automation** — kubernetes uses prow extensively; django, fastapi, next.js use GitHub Actions bots for labeling and welcome messages
- **Iterative review** — django shows 5–10 comment rounds; next.js and react show 1–3 rounds for most PRs

### Label taxonomy convergence
All repos use variants of:
- **Type labels**: bug, feature/enhancement, documentation, question
- **Resolution labels**: duplicate, wontfix, invalid, needs-more-info
- **Status labels**: in-progress, needs-review, approved, stale
- **Priority labels**: critical, high, backlog (kubernetes most explicit)
- **Component labels**: area-specific labels for routing to right reviewers

### PR size norms
| Category | Lines changed | Files changed |
|----------|--------------|---------------|
| Typo/doc fix | 1–10 | 1–3 |
| Minor bug fix | 3–50 | 1–5 |
| Moderate fix | 50–200 | 2–15 |
| Feature | 100–800 | 5–30 |
| Large feature/refactor | 800+ | 20+ |

---

## 3. Unique Patterns Per Repo

| Repo | Unique Pattern |
|------|---------------|
| kubernetes/kubernetes | `/lgtm` + `/approve` bot commands; SIG-based ownership; OWNERS files per directory; prow CI bot; size/* labels |
| facebook/react | Explicit "How did you test?" required in PR body; `Needs Browser Testing` label for manual QA gate; `React Core Team` label distinguishes insider PRs |
| django/django | Trac ticket mandatory for non-trivial changes; AI disclosure policy with specific checkbox in template; Djangonauts mentorship program; `no ticket` auto-label closes PRs |
| tiangolo/fastapi | Single-maintainer review model; `maybe-ai` label for AI-suspected content; 50+ language translation pipeline as primary contribution type |
| vercel/next.js | Fork CI approval gate (`CI approved` label) for security; Graphite stacking support; separate team labels per sub-team; React version sync automated PRs |

---

## 4. Extracted Evaluation Dimensions

Based on cross-repo analysis, these are the key dimensions Collie should evaluate when triaging PRs and issues:

### Hard Rules (Binary pass/fail)
1. **CI status** — did all automated checks pass?
2. **Required reviews** — has the minimum number of approvals been met?
3. **Linked issue/ticket** — is this PR associated with a tracked issue?
4. **CLA/contributor agreement** — has the contributor signed required agreements?
5. **Tests present** — for code changes, are tests included?
6. **Linting/formatting** — does code pass style checks?

### Soft Signals (Weighted scoring)
1. **PR description quality** — does it explain motivation and testing approach?
2. **PR size** — is it appropriately scoped or a monolithic change?
3. **Contributor history** — is this a known contributor or first-timer?
4. **Review iteration** — how many rounds of review? Unresolved comments?
5. **Label completeness** — has the PR been properly labeled?
6. **Documentation updated** — for user-facing changes, are docs updated?
7. **Breaking changes flagged** — is backward compatibility addressed?

### Escalation Triggers (Require human judgment)
1. **Security implications** — auth, permissions, crypto, data exposure changes
2. **Breaking API changes** — any change that could break existing users
3. **Large refactors** — changes touching 20+ files or 1000+ lines
4. **Architectural decisions** — new abstractions, design patterns, dependencies

### Issue Management Dimensions
1. **Reproducibility** — does the issue have a reproduction case?
2. **Duplicate detection** — does this match an existing open issue?
3. **Staleness** — has the issue been inactive for too long?
4. **Feature vs. bug** — is this a bug report or feature request?
5. **Component routing** — which team/SIG/area owns this?
6. **Priority classification** — critical/important/backlog?
