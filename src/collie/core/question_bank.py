"""
Collie sit interview question bank.
Derived from Phase 0 research on 5 exemplary repos:
- kubernetes/kubernetes (prow bot, OWNERS-based review, SIG structure)
- facebook/react (CLA, explicit test description, single-approver model)
- django/django (Trac ticket mandate, AI disclosure, 2+ reviewer norm)
- tiangolo/fastapi (single-maintainer, maybe-ai label, translation pipeline)
- vercel/next.js (fork CI gate, Graphite stacking, sub-team labels)
"""

QUESTION_BANK = [
    # ─────────────────────────────────────────────────────────────────────
    # CATEGORY: hard_rules
    # Binary pass/fail gates found in every analyzed repo.
    # ─────────────────────────────────────────────────────────────────────
    {
        "id": "ci_policy",
        "category": "hard_rules",
        "text": "What is your CI policy for PRs?",
        "confirmation_template": (
            "I found CI workflows in .github/workflows/. "
            "Should all CI checks pass before a PR can be merged? "
            "Or are some checks advisory-only?"
        ),
        "fallback_text": (
            "Do you require CI to pass before merging PRs? Are there any checks that can be bypassed by maintainers?"
        ),
    },
    {
        "id": "required_reviews",
        "category": "hard_rules",
        "text": "How many reviewer approvals are required before merging?",
        "confirmation_template": (
            "I can see recent PRs were merged with {review_count} approval(s). "
            "Is that your minimum, or do different change types require more?"
        ),
        "fallback_text": ("How many approvals do you require? Do bug fixes need the same count as new features?"),
    },
    {
        "id": "cla_requirement",
        "category": "hard_rules",
        "text": "Do contributors need to sign a CLA or contributor agreement?",
        "confirmation_template": (
            "I found a CLA reference in your CONTRIBUTING.md. Should unsigned PRs be blocked automatically?"
        ),
        "fallback_text": (
            "Do you require a Contributor License Agreement (CLA) or Developer Certificate "
            "of Origin (DCO)? Should unsigned PRs be rejected automatically?"
        ),
    },
    {
        "id": "linked_issue_required",
        "category": "hard_rules",
        "text": "Do PRs need to reference a linked issue or ticket before being merged?",
        "confirmation_template": (
            "Your CONTRIBUTING.md mentions opening issues before PRs. "
            "Should PRs without a linked issue be flagged or rejected?"
        ),
        "fallback_text": (
            "Should every PR reference an existing issue? Or is it okay for small fixes (typos, docs) to skip this?"
        ),
    },
    {
        "id": "linting_required",
        "category": "hard_rules",
        "text": "Is linting and code formatting a hard requirement for merge?",
        "confirmation_template": (
            "I found linting config files ({linters}). Should PRs that fail these checks be blocked from merging?"
        ),
        "fallback_text": (
            "Do you enforce code style with a linter (ESLint, Ruff, Black, gofmt, etc.)? "
            "Is a formatting failure a blocker or just a warning?"
        ),
    },
    {
        "id": "tests_required",
        "category": "hard_rules",
        "text": "Are tests required for all code-changing PRs?",
        "confirmation_template": (
            "I can see your test suite in {test_path}. "
            "Should PRs that modify code but add no tests be flagged or rejected?"
        ),
        "fallback_text": (
            "Do you require tests for bug fixes? For new features? "
            "Are there categories of changes (e.g., docs, refactors) exempt from this?"
        ),
    },
    {
        "id": "branch_target_policy",
        "category": "hard_rules",
        "text": "Which branch should PRs target, and are there rules for backports?",
        "confirmation_template": (
            "Your default branch is {default_branch}. "
            "Should PRs that target the wrong branch be redirected automatically?"
        ),
        "fallback_text": (
            "What is your main development branch? Do you have release branches? "
            "How do you handle backport PRs for older versions?"
        ),
    },
    # ─────────────────────────────────────────────────────────────────────
    # CATEGORY: soft_signals
    # Weighted scoring signals found across analyzed repos.
    # ─────────────────────────────────────────────────────────────────────
    {
        "id": "pr_description_quality",
        "category": "soft_signals",
        "text": "What should a good PR description include?",
        "confirmation_template": (
            "Your PR template asks for {template_fields}. "
            "Should PRs with empty or very short descriptions be flagged for review?"
        ),
        "fallback_text": (
            "What fields do you expect in a PR description? "
            "(e.g., motivation, how you tested it, screenshots for UI changes) "
            "React closes PRs with empty 'How did you test this?' fields."
        ),
    },
    {
        "id": "pr_size_norms",
        "category": "soft_signals",
        "text": "What is your policy on PR size?",
        "confirmation_template": (
            "Recent merged PRs range from {min_lines} to {max_lines} lines changed. "
            "At what point should a PR be flagged as too large to review effectively?"
        ),
        "fallback_text": (
            "Do you have a preferred maximum PR size? "
            "Kubernetes labels PRs size/XS through size/XXL and asks authors to split large PRs. "
            "What threshold would you use to suggest splitting?"
        ),
    },
    {
        "id": "contributor_trust",
        "category": "soft_signals",
        "text": "How do you distinguish between trusted contributors and first-time contributors?",
        "confirmation_template": (
            "I can see {org_members} organization members in recent PR activity. "
            "Should first-time contributors get a welcome message and checklist? "
            "(Django does this automatically.)"
        ),
        "fallback_text": (
            "Do you treat PRs from first-time contributors differently? "
            "For example: require more reviewers, add a welcome message, "
            "or require CI approval before running on fork PRs?"
        ),
    },
    {
        "id": "documentation_requirement",
        "category": "soft_signals",
        "text": "When should documentation updates be required alongside code changes?",
        "confirmation_template": (
            "I found documentation at {docs_path}. "
            "Should PRs that change user-facing behavior be required to update docs?"
        ),
        "fallback_text": (
            "Do you require documentation updates for user-facing changes? "
            "For new features? For changed behavior? For deprecated APIs?"
        ),
    },
    {
        "id": "commit_message_convention",
        "category": "soft_signals",
        "text": "Do you enforce commit message conventions?",
        "confirmation_template": (
            "I found {convention_hint} in your repo. Should PRs with non-conforming commit messages be flagged?"
        ),
        "fallback_text": (
            "Do you use Conventional Commits, Angular commit style, or another format? "
            "Should the commit message format be checked before merge? "
            "Django uses 'Fixed #NNNNN -- Description' as a strict convention."
        ),
    },
    {
        "id": "review_turnaround_expectation",
        "category": "soft_signals",
        "text": "What is your expected review turnaround time before a PR is considered stale?",
        "confirmation_template": (
            "I found a stale label in your repo config. "
            "After how many days without reviewer response should a PR be flagged?"
        ),
        "fallback_text": (
            "After how many days without reviewer activity should a PR be flagged as stale? "
            "Should the author be notified? Should it be auto-closed after further inactivity?"
        ),
    },
    {
        "id": "ai_contribution_policy",
        "category": "soft_signals",
        "text": "What is your policy on AI-assisted contributions?",
        "confirmation_template": (
            "Django has an explicit AI disclosure checkbox in PRs. "
            "FastAPI labels suspected AI PRs with 'maybe-ai'. "
            "Would you like to require AI disclosure or flag suspected AI-generated content?"
        ),
        "fallback_text": (
            "Do you require contributors to disclose if they used AI tools (Copilot, Claude, etc.)? "
            "Do you want AI-assisted PRs treated differently in review?"
        ),
    },
    {
        "id": "unresolved_review_comments",
        "category": "soft_signals",
        "text": "How do you handle unresolved review comments at merge time?",
        "confirmation_template": (
            "Some recent PRs show multiple rounds of back-and-forth before approval. "
            "Should PRs with unresolved review threads be blocked from merging?"
        ),
        "fallback_text": (
            "Should a PR be blocked from merging if it has unresolved review comments? "
            "Or is it up to the reviewer to re-approve after changes?"
        ),
    },
    # ─────────────────────────────────────────────────────────────────────
    # CATEGORY: escalation
    # Triggers found across repos that require elevated human review.
    # ─────────────────────────────────────────────────────────────────────
    {
        "id": "breaking_change_policy",
        "category": "escalation",
        "text": "How should breaking changes be handled?",
        "confirmation_template": (
            "I found a 'Type: Breaking Change' label in your repo. "
            "Should breaking changes require a special approval process or "
            "additional reviewers beyond the normal minimum?"
        ),
        "fallback_text": (
            "What defines a breaking change for your project? "
            "Do breaking changes require a deprecation period, a major version bump, "
            "or a design document before a PR can be opened?"
        ),
    },
    {
        "id": "security_review_policy",
        "category": "escalation",
        "text": "Do security-sensitive changes require a dedicated security review?",
        "confirmation_template": (
            "Your codebase includes {security_areas}. "
            "Should PRs touching authentication, authorization, or cryptography "
            "be automatically flagged for security review?"
        ),
        "fallback_text": (
            "Do you have a security team or designated security reviewers? "
            "Which types of changes trigger mandatory security review? "
            "(e.g., auth flows, permission checks, encryption, external API calls)"
        ),
    },
    {
        "id": "large_refactor_policy",
        "category": "escalation",
        "text": "What is your process for large refactors or architectural changes?",
        "confirmation_template": (
            "Some recent PRs touched {max_files}+ files. "
            "Should large refactors (e.g., 20+ files or 1000+ lines) require "
            "a design document or pre-approval before a PR is opened?"
        ),
        "fallback_text": (
            "For large refactors or architectural changes, do you require: "
            "a design doc (RFC), issue discussion, or sign-off from a lead "
            "before the PR is submitted? What size threshold triggers this?"
        ),
    },
    {
        "id": "dependency_addition_policy",
        "category": "escalation",
        "text": "Does adding a new external dependency require special approval?",
        "confirmation_template": (
            "I found Dependabot or dependency update PRs in your recent activity. "
            "Should PRs that add new dependencies (not updates) require "
            "additional review or a security audit?"
        ),
        "fallback_text": (
            "Do contributors need approval before adding a new external dependency? "
            "Do you vet dependencies for security, license compatibility, or bundle size?"
        ),
    },
    # ─────────────────────────────────────────────────────────────────────
    # CATEGORY: issue_management
    # Issue triage patterns from all 5 repos.
    # ─────────────────────────────────────────────────────────────────────
    {
        "id": "reproduction_required",
        "category": "issue_management",
        "text": "Do bug reports require a reproduction case before being triaged?",
        "confirmation_template": (
            "I found a 'please add a complete reproduction' label in your repo "
            "(used by Next.js to auto-close issues without reproductions). "
            "Should issues without a repro link be automatically flagged or closed?"
        ),
        "fallback_text": (
            "Should bug reports without a reproducible test case be auto-closed "
            "or put in a 'needs repro' state? "
            "How long should you wait before closing them?"
        ),
    },
    {
        "id": "stale_issue_policy",
        "category": "issue_management",
        "text": "What is your policy for stale issues?",
        "confirmation_template": (
            "I found a stale label in your repo. "
            "After how many days of inactivity should an issue be marked stale? "
            "After how many additional days should it be auto-closed?"
        ),
        "fallback_text": (
            "After how many days without activity should an issue be labeled 'stale'? "
            "Should a warning be posted before closing? "
            "Are some issue types (e.g., confirmed bugs) exempt from staleness?"
        ),
    },
    {
        "id": "duplicate_detection_policy",
        "category": "issue_management",
        "text": "How do you handle duplicate issues?",
        "confirmation_template": (
            "Your repo has a 'duplicate' label. "
            "Should Collie suggest potential duplicates before a new issue is confirmed? "
            "Who has authority to mark issues as duplicate?"
        ),
        "fallback_text": (
            "Should new issues be checked for duplicates automatically? "
            "If a duplicate is found, should the newer issue be closed immediately "
            "or kept open with a reference?"
        ),
    },
    {
        "id": "feature_request_triage",
        "category": "issue_management",
        "text": "How should feature requests be handled differently from bug reports?",
        "confirmation_template": (
            "Your repo has separate 'bug' and 'feature'/'enhancement' labels. "
            "Should feature requests require community voting or team discussion "
            "before being accepted?"
        ),
        "fallback_text": (
            "Do you want a different workflow for feature requests vs. bugs? "
            "For example: features might need a 'community-feedback' period or "
            "a team vote before being added to the roadmap."
        ),
    },
    {
        "id": "issue_label_taxonomy",
        "category": "issue_management",
        "text": "What label categories do you use to organize issues?",
        "confirmation_template": (
            "I found these existing labels: {existing_labels}. "
            "Are these the right categories, or would you like to add/remove any?"
        ),
        "fallback_text": (
            "What categories of labels do you need? Common patterns include: "
            "type (bug/feature/docs/question), "
            "priority (critical/high/medium/low), "
            "status (triage/confirmed/in-progress/blocked), "
            "component (which part of the codebase). "
            "Which of these apply to your project?"
        ),
    },
    {
        "id": "issue_assignment_policy",
        "category": "issue_management",
        "text": "How are issues assigned to contributors?",
        "confirmation_template": (
            "Kubernetes uses OWNERS files to auto-assign reviewers by area. "
            "Would you like Collie to suggest assignees based on file ownership or past contributions?"
        ),
        "fallback_text": (
            "Do contributors self-assign issues, or does a maintainer assign them? "
            "Should 'good first issue' items be reserved until someone claims them? "
            "How long can someone hold an issue before it's reassigned?"
        ),
    },
    {
        "id": "canary_verification_policy",
        "category": "issue_management",
        "text": "Should issues be verified against the latest release or pre-release before being confirmed?",
        "confirmation_template": (
            "Next.js uses a 'please verify canary' label to ask reporters to check the latest build. "
            "Should issues be required to confirm they reproduce on {latest_version} before being confirmed?"
        ),
        "fallback_text": (
            "Should bug reporters be asked to verify the issue exists in the latest release "
            "before the issue is confirmed? This reduces noise from already-fixed bugs."
        ),
    },
    # ─────────────────────────────────────────────────────────────────────
    # CATEGORY: project_direction
    # Strategic and release-process questions from all 5 repos.
    # ─────────────────────────────────────────────────────────────────────
    {
        "id": "backward_compatibility_policy",
        "category": "project_direction",
        "text": "What is your backward compatibility guarantee?",
        "confirmation_template": (
            "Your repo has breaking change tracking. "
            "Do you follow semantic versioning? "
            "How many major versions do you actively support?"
        ),
        "fallback_text": (
            "Do you guarantee backward compatibility within a major version? "
            "Do you have a deprecation policy before removing features? "
            "How many previous versions do you backport security fixes to?"
        ),
    },
    {
        "id": "release_process",
        "category": "project_direction",
        "text": "How is your release process managed?",
        "confirmation_template": (
            "I found release-related labels ({release_labels}) in your repo. "
            "Who has authority to cut a release? Is there a release checklist or automation?"
        ),
        "fallback_text": (
            "How do you manage releases? "
            "(e.g., automated on merge to main, manual tag, CalVer, SemVer) "
            "Do you have release candidates or beta channels before stable releases?"
        ),
    },
    {
        "id": "dependency_update_policy",
        "category": "project_direction",
        "text": "How do you manage dependency updates?",
        "confirmation_template": (
            "I found Dependabot configuration in your repo. "
            "Should dependency updates be auto-merged when CI passes, "
            "or do they require human review?"
        ),
        "fallback_text": (
            "Do you use Dependabot, Renovate, or manual dependency management? "
            "Should patch updates auto-merge? Minor updates? Major updates? "
            "Do you pin dependency versions?"
        ),
    },
    {
        "id": "external_contributions_scope",
        "category": "project_direction",
        "text": "What types of contributions are you actively seeking from the community?",
        "confirmation_template": (
            "Your 'good first issue' label has {gfi_count} open issues. "
            "Beyond those, what areas are you most open to external contributions in? "
            "(features, docs, translations, tests, bug fixes)"
        ),
        "fallback_text": (
            "Are you open to community contributions for new features, "
            "or mainly bug fixes and documentation? "
            "Are there areas of the codebase that are off-limits for external PRs?"
        ),
    },
    {
        "id": "performance_requirements",
        "category": "project_direction",
        "text": "Do PRs need to demonstrate no performance regressions?",
        "confirmation_template": (
            "I found performance/benchmark tooling in your repo ({perf_tools}). "
            "Should PRs that might affect performance include benchmark results?"
        ),
        "fallback_text": (
            "Do you track performance benchmarks? "
            "Should PRs that could affect performance be required to include "
            "benchmark comparisons before/after the change?"
        ),
    },
    {
        "id": "changelog_policy",
        "category": "project_direction",
        "text": "How do you maintain a changelog or release notes?",
        "confirmation_template": (
            "Kubernetes requires release notes for user-facing changes. "
            "React and Django maintain separate changelogs. "
            "Should PRs include a changelog entry or release note as a merge requirement?"
        ),
        "fallback_text": (
            "Do you maintain a CHANGELOG.md, release notes in PRs, or generate them automatically? "
            "Should contributors be required to add changelog entries for user-facing changes?"
        ),
    },
    {
        "id": "code_ownership_model",
        "category": "project_direction",
        "text": "Do you use a code ownership model (CODEOWNERS, OWNERS files) to route reviews?",
        "confirmation_template": (
            "I found {ownership_file} in your repo. "
            "Should Collie use this to suggest reviewers automatically when a PR is opened?"
        ),
        "fallback_text": (
            "Do you have CODEOWNERS or similar ownership files to route PRs to the right reviewers? "
            "If not, how do you ensure the right people review changes to sensitive areas?"
        ),
    },
]
