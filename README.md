<p align="center">
  <img src="assets/mascot.png" alt="Collie" width="400">
</p>

<h1 align="center">Collie</h1>

<p align="center">
  <strong>AI-powered GitHub repository triage for solo maintainers</strong>
</p>

<p align="center">
  <em>A Border Collie herding 500+ issues and PRs so you don't have to.</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> |
  <a href="#commands">Commands</a> |
  <a href="#how-it-works">How It Works</a> |
  <a href="#mcp-setup">MCP Setup</a> |
  <a href="#github-action">GitHub Action</a>
</p>

---

## The Problem

You maintain an open-source project. It got popular. Now you have 500+ open issues and PRs, and you can't read them all. Dependabot PRs pile up, stale feature requests linger, and good contributions get lost in the noise.

**Collie solves this.** It learns your merge philosophy through a Socratic interview, then triages every issue and PR — recommending merge, close, hold, or escalate — so you only review what matters.

## Quick Start

```bash
# Install
pip install collie

# Set up authentication
export GITHUB_TOKEN=ghp_your_token_here
export ANTHROPIC_API_KEY=sk-ant-your_key_here  # Optional: enables AI analysis

# Teach Collie your merge philosophy
collie sit owner/repo

# Let Collie analyze your repo
collie bark owner/repo

# Review and approve recommendations
collie approve owner/repo 142 237 301

# When you trust Collie, unleash it
collie unleash owner/repo
```

## Commands

All commands follow a dog training theme:

| Command | What it does |
|---------|-------------|
| `collie sit <repo>` | **Interview** — Analyze your repo and create a merge philosophy through Q&A |
| `collie bark <repo>` | **Triage** — Analyze all open issues/PRs and generate recommendations |
| `collie approve <repo> <numbers...>` | **Execute** — Approve and run recommended actions (merge, close, label, comment) |
| `collie approve <repo> --all` | **Execute all** — Approve all pending recommendations |
| `collie reject <repo> <number> -r "reason"` | **Reject** — Reject a recommendation and refine your philosophy |
| `collie shake-hands <repo>` | **Revise** — Modify your merge philosophy |
| `collie unleash <repo>` | **Activate** — Switch from training to active mode (enable execution) |
| `collie leash <repo>` | **Deactivate** — Switch back to training mode |
| `collie status <repo>` | **Status** — Show current mode, rules, and settings |
| `collie mcp` | **MCP Server** — Start the MCP server for Claude Desktop / Claude Code integration |

## How It Works

```
collie sit ──→ Philosophy (Discussion)
                    │
collie bark ──→ 3-Tier Analysis ──→ Queue (Discussion)
                    │                     │
              T1: Rules ──→ T2: Summary ──→ T3: Deep Review
              (free)      (1 LLM call)    (N LLM calls)
                    │                     │
              Recommendations:  merge / close / hold / escalate
                                          │
collie approve ──→ Execute ──→ GitHub API (merge, close, comment, label)
                    │
              Reject? ──→ Micro-update ──→ Philosophy refined
```

### Three-Tier Analysis

| Tier | What | Cost | When |
|------|------|------|------|
| **T1** | Rule-based scan | Free | Always — CI status, hard rules |
| **T2** | AI summary | ~$0.01/item | When T1 can't decide |
| **T3** | Full diff review | ~$0.10/item | When T2 is uncertain or escalation rules trigger |

### Conservative Merge Policy

- Merge is only recommended when analysis is **100% complete**
- Partial analysis (large diffs, unanalyzable files) → automatic **hold**
- All actions require **human approval** before execution (belt + suspenders safety)

### Training Mode

New repos start in **training mode**:
1. `collie bark` generates recommendations but won't execute
2. You review recommendations to verify quality
3. When satisfied, `collie unleash` enables execution
4. `collie leash` returns to training anytime

## Storage

Collie uses **GitHub Discussions** as its only storage — no external database needed:

- **Philosophy**: A Discussion post with your merge rules (YAML) + philosophy (natural language)
- **Queue**: A living document with recommendations, checkboxes for approval, and execution status
- Discussions are auto-created if you have admin access

## MCP Setup

Use Collie as an MCP server in Claude Desktop or Claude Code:

```json
{
  "mcpServers": {
    "collie": {
      "command": "uvx",
      "args": ["collie"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token",
        "ANTHROPIC_API_KEY": "sk-ant-your_key"
      }
    }
  }
}
```

Available MCP tools: `collie_sit_analyze`, `collie_sit_save`, `collie_bark`, `collie_approve`, `collie_reject`, `collie_unleash`, `collie_leash`, `collie_status`

## GitHub Action

Run Collie on a schedule with GitHub Actions:

```yaml
# .github/workflows/collie.yml
name: Collie Daily Triage
on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:

jobs:
  triage:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      pull-requests: write
      discussions: write
    steps:
      - uses: shaun0927/collie@main
        with:
          github-token: ${{ secrets.COLLIE_GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          cost-cap: '30'
```

## Configuration

### Config File (recommended)

Create `~/.collie/config.yaml` to avoid setting environment variables every time:

```yaml
github_token: ghp_your_token_here
anthropic_api_key: sk-ant-your_key_here
default_repo: owner/repo
```

```bash
mkdir -p ~/.collie
chmod 700 ~/.collie
# Create config.yaml with your tokens, then:
chmod 600 ~/.collie/config.yaml
```

> **Security:** Collie warns if the config file is readable by others. Environment variables take precedence over the config file.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT with repo + discussion write access |
| `ANTHROPIC_API_KEY` | No | Enables AI analysis (T2/T3). Without it, only T1 rule-based scanning works |

### Philosophy Tuning

After `collie sit`, you can tune parameters in the Discussion:

```yaml
tuning:
  confidence_threshold: 0.9   # How sure Collie must be to recommend merge
  analysis_depth: t2           # t1 (rules only), t2 (+ AI summary), t3 (+ deep review)
  cost_cap_per_bark: 50.0      # Max LLM cost in USD per bark run
```

## FAQ

**Q: Can Collie merge PRs automatically?**
A: Only after you `collie unleash` and explicitly `collie approve`. Collie never acts without your approval.

**Q: What if Collie recommends merging a bad PR?**
A: Two safety layers protect you: (1) Collie only recommends merge for fully analyzed PRs, (2) you must approve before execution. Reject bad recommendations with `collie reject` to improve the philosophy.

**Q: How much does it cost to run?**
A: T1 analysis is free. T2/T3 use the Anthropic API. A typical 500-item repo costs $10-50 per full scan, and incremental runs (daily) are much cheaper.

**Q: Does it work with private repos?**
A: Not yet — v1 supports public repos only. Private repo support is planned for v2.

## License

MIT

## Credits

Built with the [Ouroboros](https://github.com/Q00/ouroboros) specification-first methodology.
