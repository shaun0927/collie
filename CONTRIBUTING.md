# Contributing to Collie

## Development Setup

```bash
# Clone
git clone https://github.com/shaun0927/collie.git
cd collie

# Install with dev dependencies
pip install -e ".[dev]"

# Verify
collie --version
pytest
```

## Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_analyzer.py -v

# With coverage
pytest --cov=collie
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Line length is 120 characters.

## Project Structure

```
src/collie/
├── cli/main.py          # CLI entry point (click)
├── mcp/server.py        # MCP server for Claude Desktop
├── commands/             # Command implementations
│   ├── sit.py           # Repository analysis + interview
│   ├── bark.py          # 3-tier analysis pipeline
│   ├── approve.py       # Approval + execution
│   ├── shake_hands.py   # Philosophy revision
│   └── mode.py          # Training/active mode
├── core/                 # Core logic
│   ├── analyzer.py      # T1/T2/T3 analysis tiers
│   ├── models.py        # Data models
│   ├── cost_tracker.py  # LLM cost management
│   ├── incremental.py   # Delta processing
│   ├── llm_client.py    # Anthropic API wrapper
│   ├── prompts.py       # LLM prompt templates
│   ├── question_bank.py # Interview questions
│   └── stores/          # Discussion-backed storage
├── github/              # GitHub API clients
│   ├── graphql.py       # GraphQL (read)
│   └── rest.py          # REST (write)
└── auth/                # Authentication
    └── providers.py     # PAT + OAuth
```

## Pull Request Process

1. Create a feature branch
2. Write tests for new functionality
3. Ensure `ruff check` and `pytest` pass
4. Submit PR with clear description
