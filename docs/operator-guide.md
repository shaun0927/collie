# Collie Operator Guide

This guide explains how to roll out and operate Collie safely after the hardening work in PR-01 through PR-07.

## 1. Recommended rollout sequence

1. **Install and authenticate**
   - Configure `GITHUB_TOKEN`
   - Configure an LLM backend (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `LLM_PROVIDER` + `LLM_API_KEY`), or rely on Codex CLI locally
2. **Run `collie sit owner/repo`**
   - Review the generated philosophy carefully
   - Treat the first philosophy as a draft, not a final policy
3. **Stay in training mode**
   - Run `collie bark owner/repo`
   - Review recommendations in the queue discussion
   - Reject poor recommendations and refine policy with `collie reject`
4. **Only then switch to active mode**
   - Run `collie unleash owner/repo`
   - Continue approving explicitly with `collie approve ...`

## 2. Approval model

Collie now distinguishes between **presentation** and **authorization**.

- The queue discussion is human-readable and useful for review.
- Verified approvals are recorded as structured approval records bound to a recommendation payload hash.
- `collie approve owner/repo <numbers...>` is the canonical approval + execution path.
- `collie approve owner/repo --all` consumes **verified approvals only**.
- A checked markdown checkbox alone is **not** a trustworthy authorization primitive.

## 3. Execution paths in active mode

For merge recommendations, Collie can now choose among multiple execution paths based on GitHub-native metadata:

- **direct merge** — used when governance metadata allows an immediate merge
- **auto-merge** — used when required checks are pending but the pull request can be queued for automatic merge once checks pass
- **merge queue** — used when merge queue is required and supported
- **blocked** — used when draft status, changes requested, merge conflicts, failing checks, or missing governance support prevent execution

Queue and execution results preserve the chosen execution path when possible.

## 4. CLI usage

```bash
# Inspect current state
collie status owner/repo

# Analyze repository policy inputs
collie sit owner/repo

# Refresh triage queue
collie bark owner/repo

# Approve one or more specific items
collie approve owner/repo 142 237

# Execute all verified approvals
collie approve owner/repo --all

# Refine philosophy after a bad recommendation
collie reject owner/repo 142 -r "needs stronger security review"
```

## 5. MCP usage

Start the MCP server with:

```bash
collie mcp
```

For `uvx`, use:

```json
{
  "mcpServers": {
    "collie": {
      "command": "uvx",
      "args": ["collie", "mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token",
        "ANTHROPIC_API_KEY": "sk-ant-your_key"
      }
    }
  }
}
```

Available tools:
- `collie_sit_analyze`
- `collie_sit_save`
- `collie_bark`
- `collie_approve`
- `collie_reject`
- `collie_unleash`
- `collie_leash`
- `collie_status`

## 6. GitHub Action usage

The bundled GitHub Action runs **bark** on a schedule and refreshes the queue.

It is best described as:
- fetch open issues/PRs
- analyze them
- update the queue discussion
- preserve queue state / incremental metadata

It should **not** be documented as an autonomous execution engine by itself.

## 7. Safety checklist before enabling active mode

- [ ] Philosophy reviewed and edited by a maintainer
- [ ] At least one bark run in training mode reviewed manually
- [ ] Rejection/micro-update loop tested at least once
- [ ] Verify `approve` on a sandbox repo first
- [ ] Verify blocked/direct/auto-merge/merge-queue outcomes on a sandbox repo if relevant
- [ ] Confirm Discussions are enabled and writable
- [ ] Confirm repository permissions and branch protection behavior match expectations

## 8. Recommended post-deploy checks

- [ ] `collie status owner/repo` reports expected mode and queue counts
- [ ] `collie bark owner/repo` updates the queue without losing prior verified approval state
- [ ] Explicit `collie approve owner/repo <numbers...>` records verified approvals and execution results
- [ ] `collie approve owner/repo --all` consumes only verified approvals
- [ ] For protected/default branches, direct merge is not attempted when blocked by governance metadata
- [ ] For pending checks, auto-merge is used when supported
- [ ] For merge-queue-required repos, merge queue is used or a clear blocked reason is surfaced

## 9. Known operational caveats

See [`docs/known-limitations.md`](./known-limitations.md).
