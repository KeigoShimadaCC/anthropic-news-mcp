# Getting started

This page walks through installing, configuring, and running the server end to end.

## Prerequisites

- Python 3.11 or newer (the `.python-version` file pins to 3.11)
- A POSIX shell. Commands assume bash or zsh
- Optional: a GitHub personal access token to raise the GitHub API rate limit from 60 to 5,000 requests per hour

## Install

The repo is a standard `pyproject.toml` Python package built with hatchling.

### From source (development)

```bash
git clone https://github.com/KeigoShimadaCC/anthropic-news-mcp
cd anthropic-news-mcp
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`[dev]` adds `pytest`, `pytest-asyncio`, `mypy`, `ruff`, `pre-commit`, and `PyYAML`. Two extras are also defined:

- `[eval]` — `anthropic` SDK plus `PyYAML` for the LLM judge eval harness
- `[remote]` — `PyJWT[crypto]`, `starlette`, `uvicorn` for Streamable HTTP deployment

### From a package index

The README documents installation via `uv tool install` or `pipx install`, but at the time of writing the package is not published. Use the source install above.

## Configure an MCP client

The server speaks MCP over stdio. Both Claude Desktop and Cursor accept the same shape of config.

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "uvx",
      "args": ["anthropic-news-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_optional_token"
      }
    }
  }
}
```

Restart Claude Desktop. The 15 tools register automatically.

### Cursor

Edit `~/.cursor/mcp.json` (or use Settings → MCP → Edit config) with the same JSON shape.

### Local development invocation

If you have the repo cloned and the venv set up, point the client at the local entry point instead:

```json
{
  "command": "/absolute/path/to/anthropic-news-mcp/.venv/bin/anthropic-news-mcp"
}
```

Or run it directly from a shell:

```bash
.venv/bin/anthropic-news-mcp
# equivalent
.venv/bin/python -m anthropic_news_mcp
```

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GITHUB_TOKEN` | No | Raises GitHub API rate limit. No scopes needed for public repos. |
| `ANTHROPIC_NEWS_MCP_CACHE_DB` | No | Override the SQLite cache path. Must be an absolute path. Default: `~/.cache/anthropic-news-mcp/cache.db`. |
| `XDG_CACHE_HOME` | No | Override the parent cache directory. The server warns if the directory is world-readable. |
| `ANTHROPIC_API_KEY` | Eval only | Required for `evals/run_eval.py`. |

The remote-only variables (`ANTHROPIC_NEWS_MCP_AUTH_*`, `ANTHROPIC_NEWS_MCP_ALLOWED_*`) are documented in [Remote ASGI deployment](../apps/remote-asgi.md).

A reference template lives at `.env.example`.

## First call

After configuring the client, a few prompts to verify everything works:

> *"Ping the anthropic-news server."*

This calls the `ping` tool and returns `{"status": "ok", "server": "anthropic-news-mcp", "version": "0.1.0"}`.

> *"List the news sources you have configured."*

This calls `list_sources` and returns the seventeen registered sources.

> *"What's the latest from Anthropic?"*

This calls `get_recent_updates` with default parameters. The first call populates the cache; subsequent calls within each source's TTL serve from cache.

## Run the test suite

All tests are offline and use frozen fixtures.

```bash
.venv/bin/pytest tests/ -v          # full suite (146+ tests)
.venv/bin/pytest tests/test_cache.py -v
.venv/bin/pytest tests/test_server.py::test_ping -v
```

## Lint, format, type check

```bash
.venv/bin/ruff check .
.venv/bin/ruff format .
.venv/bin/mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
```

These three commands plus `pytest -q` and `python evals/run_offline_eval.py` make up the CI pipeline. See [Tooling](../how-to-contribute/tooling.md) for details.

## Run the deterministic offline eval

```bash
.venv/bin/python evals/run_offline_eval.py
.venv/bin/python evals/run_offline_eval.py --ids offline-01,offline-05
```

The offline eval seeds a temporary SQLite cache and validates eight deterministic tool checks. Results land in `evals/results/`.

## Run the live source audit

The audit is opt-in because it makes live HTTP requests:

```bash
.venv/bin/anthropic-news-audit
.venv/bin/anthropic-news-audit --sources anthropic-status,anthropic-engineering
.venv/bin/anthropic-news-audit --json evals/results/source_audit.json
.venv/bin/anthropic-news-audit --strict
```

See [Audit CLI](../apps/audit-cli.md).

## Next steps

- [Architecture](./architecture.md) — how the pieces fit together
- [How to contribute](../how-to-contribute/index.md) — workflow and conventions
- [Adding a new source](../how-to-contribute/development-workflow.md) — the two-file recipe
