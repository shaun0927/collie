<p align="center">
  <img src="assets/mascot.png" alt="Collie" width="400">
</p>

<h1 align="center">Collie</h1>

<p align="center">
  <strong>Codify your team's merge philosophy. Let AI triage the rest.</strong>
</p>

<p align="center">
  <em>A Border Collie that herds 500+ issues and PRs — so your team reviews what matters, not everything.</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> |
  <a href="#commands">Commands</a> |
  <a href="#how-it-works">How It Works</a> |
  <a href="#why-teams-love-collie">For Teams</a> |
  <a href="#mcp-setup">MCP Setup</a> |
  <a href="#github-action">GitHub Action</a> |
  <a href="#operator-guide">Operator Guide</a>
</p>

---

## The Problem

**Solo maintainer?** 500+ open issues. Dependabot PRs piling up. Good contributions buried in noise. You can't read them all.

**Growing team?** Everyone reviews differently. New members don't know what to merge. Tribal knowledge lives in Slack threads that nobody can find. Your best reviewer goes on vacation and the queue stalls.

**Collie solves both.** It captures your merge philosophy as a living document, then applies it to every issue and PR — recommending merge, close, hold, or escalate. Your standards stay consistent whether you have 1 reviewer or 20.

## Quick Start

```bash
# Install
pip install collie

# Set up authentication
export GITHUB_TOKEN=ghp_your_token_here
export ANTHROPIC_API_KEY=sk-ant-your_key_here  # Optional: enables AI analysis
# Or just install Codex CLI — Collie auto-detects it (no API key needed)

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
| `collie approve <repo> <numbers...>` | **Execute** — Record verified approval(s) and run the selected recommendation(s) |
| `collie approve <repo> --all` | **Execute all** — Execute all **verified** approvals |
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
- Verified approvals are bound to a recommendation payload, not just an item number
- Governance-aware execution can choose **direct merge**, **auto-merge**, **merge queue**, or **blocked**

### Training Mode

New repos start in **training mode**:
1. `collie bark` generates recommendations but won't execute
2. You review recommendations to verify quality
3. When satisfied, `collie unleash` enables execution
4. `collie leash` returns to training anytime

## Why Teams Love Collie

Collie isn't just a triage bot. It's a **decision-making system** built on GitHub Discussions.

| Pain point | How Collie fixes it |
|---|---|
| "What's our policy on dependabot PRs?" | Written in the Philosophy Discussion — anyone can read it |
| New team member doesn't know what to approve | Philosophy + Queue give instant context, zero onboarding lag |
| Senior reviewer is on vacation | Collie applies their standards to every PR, consistently |
| PR reviews are subjective and inconsistent | Hard rules + escalation rules make the bar explicit |
| Nobody knows why a PR was merged/rejected | Queue tracks every decision with reasons and timestamps |
| Team standards drift over time | Every `collie reject` refines the philosophy — the team gets smarter |

### Three Ways to Use Collie

| Mode | Best for | How |
|---|---|---|
| **CLI** | Maintainers triaging manually | `collie bark` in your terminal |
| **MCP** | AI-assisted review with Claude | Claude calls `collie_approve` as a tool |
| **GitHub Action** | Scheduled queue refresh and triage | Cron job runs `collie bark` every night |

## Storage

Collie uses **GitHub Discussions** as its only storage — no external database, no config server:

- **Philosophy Discussion** — Your merge rules (YAML) + natural-language philosophy. Editable by anyone on the team. Version-tracked by GitHub's edit history.
- **Queue Discussion** — A living document with recommendations and execution results. It remains human-readable, but canonical execution state is stored structurally alongside it.
- Explicit `collie approve ...` is the canonical approval path; raw markdown checkboxes should be treated as UI state, not authoritative authorization.
- Discussions are auto-created if you have admin access

## MCP Setup

Use Collie as an MCP server in Claude Desktop or Claude Code:

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

Available MCP tools: `collie_sit_analyze`, `collie_sit_save`, `collie_bark`, `collie_approve`, `collie_reject`, `collie_unleash`, `collie_leash`, `collie_status`

## GitHub Action

Run Collie on a schedule with GitHub Actions. The bundled Action runs `collie bark` to refresh recommendations and queue state; it should not be documented as a standalone autonomous execution engine.

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
default_repo: owner/repo

# LLM provider — pick one:
anthropic_api_key: sk-ant-your_key_here  # simplest if using Claude

# Or use any provider:
# llm_provider: openai          # openai, gemini, groq, together, mistral, deepseek, ollama, codex
# llm_api_key: sk-your_key_here
# llm_model: gpt-4o             # optional: override default model
# llm_base_url: https://...     # optional: custom endpoint
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
| `ANTHROPIC_API_KEY` | No | Enables AI analysis (T2/T3) via Anthropic API |

### LLM Providers

Collie works with virtually any LLM provider. It auto-detects the best available backend:

| Provider | Setup | Default Model |
|----------|-------|---------------|
| **Anthropic** | `export ANTHROPIC_API_KEY=sk-ant-...` | `claude-sonnet-4-6` |
| **OpenAI** | `export OPENAI_API_KEY=sk-...` | `gpt-4o` |
| **Google Gemini** | `export LLM_PROVIDER=gemini LLM_API_KEY=...` | `gemini-2.5-flash` |
| **Groq** | `export LLM_PROVIDER=groq LLM_API_KEY=...` | `llama-3.3-70b-versatile` |
| **Together AI** | `export LLM_PROVIDER=together LLM_API_KEY=...` | `Llama-4-Maverick` |
| **Mistral** | `export LLM_PROVIDER=mistral LLM_API_KEY=...` | `mistral-large-latest` |
| **DeepSeek** | `export LLM_PROVIDER=deepseek LLM_API_KEY=...` | `deepseek-chat` |
| **xAI (Grok)** | `export LLM_PROVIDER=xai LLM_API_KEY=...` | `grok-3` |
| **Perplexity** | `export LLM_PROVIDER=perplexity LLM_API_KEY=...` | `sonar-pro` |
| **Fireworks AI** | `export LLM_PROVIDER=fireworks LLM_API_KEY=...` | `llama-v3p1-8b-instruct` |
| **Ollama** (local) | `export LLM_PROVIDER=ollama` | `llama3.1` (no key needed) |
| **Codex CLI** | Install `codex` CLI | `o3` (OAuth, no key needed) |
| **Custom** | `export LLM_BASE_URL=... LLM_API_KEY=...` | Any OpenAI-compatible |
| _None_ | — | T1 rule-based scanning only |

All default models use **stable aliases** that auto-upgrade with provider updates. Override anytime with `LLM_MODEL=your-model`, or set `llm_model` in `~/.collie/config.yaml`.

### Philosophy Tuning

After `collie sit`, you can tune parameters in the Discussion:

```yaml
tuning:
  confidence_threshold: 0.9   # How sure Collie must be to recommend merge
  analysis_depth: t2           # t1 (rules only), t2 (+ AI summary), t3 (+ deep review)
  cost_cap_per_bark: 50.0      # Max LLM cost in USD per bark run
```

## Operator Guide

See [`docs/operator-guide.md`](docs/operator-guide.md) for active-mode rollout guidance, approval semantics, and post-deploy checks.

## FAQ

**Q: Is this only for solo maintainers?**
A: No. Collie works for teams of any size. The Philosophy Discussion becomes your team's shared review standard — new members read it on day one, and every rejection makes it smarter.

**Q: Can Collie merge PRs automatically?**
A: Only after you `collie unleash` and use the verified approval flow (`collie approve ...`). Even in active mode, execution may resolve to direct merge, auto-merge, merge queue, or a blocked result depending on GitHub governance metadata.

**Q: What if Collie recommends merging a bad PR?**
A: Two safety layers: (1) merge is only recommended for fully analyzed PRs, (2) you must approve before execution. `collie reject -r "reason"` feeds back into the philosophy so the same mistake doesn't happen twice.

**Q: How much does it cost to run?**
A: T1 analysis is free. T2/T3 use an LLM (Anthropic API or Codex CLI). With the Anthropic API, a typical 500-item repo costs $10-50 per full scan; daily incremental runs are ~$1-5. With Codex CLI (OAuth), there's no direct API cost.

**Q: Does it work with private repos?**
A: Yes, as long as your `GITHUB_TOKEN` has access to the repo and Discussions are enabled.

## License

MIT

## Credits

Built with the [Ouroboros](https://github.com/Q00/ouroboros) specification-first methodology.
