# anthropic-news-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that aggregates
Anthropic news, Claude Code changelogs, model releases, and community signals into a single
tool surface for LLM clients like Claude Desktop and Cursor.

[![CI](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why

Anthropic ships fast. Signals land across official news, research, engineering, status,
docs release notes, support release notes, GitHub repos, Hacker News, and Reddit.
Tracking these manually is noise.

This MCP server consolidates them into four tools that any MCP client can call. The data
is cached locally in SQLite so repeat queries are sub-millisecond. One failing source never
blocks the others.

---

## What it gives Claude

| Tool | Purpose |
|------|---------|
| `list_sources` | Discover what sources are configured and their keys |
| `get_recent_updates` | The main feed — filterable by source, category, and date |
| `search_updates` | Keyword search over the local cache |
| `get_source_health` | Operational status per source (fetched when, how many items, any error) |

### Categories

`models` · `claude-code` · `research` · `policy` · `business` · `community` ·
`ops` · `engineering` · `economics`

### Sources

| Key | What it covers |
|-----|----------------|
| `anthropic-newsroom` | `anthropic.com/news` — official announcements, research, products |
| `anthropic-status` | Claude Status incidents and scheduled maintenance from `status.claude.com` |
| `anthropic-research` | Research publications from `anthropic.com/research` |
| `anthropic-engineering` | Engineering posts from `anthropic.com/engineering` |
| `anthropic-docs-claude-code` | `CHANGELOG.md` from the `anthropics/claude-code` repo |
| `anthropic-docs-api` | API release notes from `platform.claude.com` |
| `anthropic-docs-claude-apps` | Claude Apps release notes from `docs.claude.com` |
| `anthropic-docs-system-prompts` | System prompt release notes from `docs.claude.com` |
| `anthropic-support-release-notes` | Claude Help Center release notes from `support.claude.com` |
| `anthropic-economic-index` | Economic Index and Economic Research updates |
| `anthropic-business-infrastructure` | Official compute, funding, partnership, enterprise, and infrastructure updates |
| `anthropic-trust-policy` | Official RSP, safety, policy, trust, transparency, and safeguards updates |
| `anthropic-github-releases` | Releases from `claude-code`, Python/TS SDKs, MCP spec |
| `anthropic-github-events` | New repos and release events from the `anthropics` org |
| `hn-anthropic` | Hacker News stories about Anthropic/Claude (≥10 points) |
| `reddit-claude` | Hot posts from `r/ClaudeAI` and `r/anthropic` |

---

## Install

### Option A — uv (recommended)

```bash
uv tool install anthropic-news-mcp
```

### Option B — pipx

```bash
pipx install anthropic-news-mcp
```

### Option C — from source

```bash
git clone https://github.com/KeigoShimadaCC/anthropic-news-mcp
cd anthropic-news-mcp
uv pip install -e .
```

---

## Configure

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "uvx",
      "args": ["anthropic-news-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_optional_token"
      }
    }
  }
}
```

Restart Claude Desktop. The four tools will appear automatically.

### Cursor

Edit `~/.cursor/mcp.json` (or Settings → MCP → Edit config):

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "uvx",
      "args": ["anthropic-news-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_optional_token"
      }
    }
  }
}
```

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GITHUB_TOKEN` | No | Raises GitHub API rate limit from 60 → 5,000 req/hr. Get one at [github.com/settings/tokens](https://github.com/settings/tokens) (no scopes needed for public repos). |
| `ANTHROPIC_API_KEY` | Eval only | Required to run `evals/run_eval.py`. |

No API key is required for the official Anthropic, Claude Status, docs, or support sources.

---

## Try it

After configuring, ask Claude:

> *"What's the latest from Anthropic?"*

> *"Did Claude Code ship anything this week?"*

> *"Search for items about MCP."*

> *"What's the community saying about Claude on Reddit right now?"*

> *"List the news sources you have configured."*

---

## How it works

```
Claude Desktop / Cursor
        │
        │  MCP stdio
        ▼
 anthropic-news-mcp (FastMCP server)
        │
        ├─ list_sources
        ├─ get_recent_updates ──► async gather across all sources
        ├─ search_updates      ──► SQLite FTS (substring)
        └─ get_source_health
                │
                ▼
        SQLite cache (~/.cache/anthropic-news-mcp/cache.db)
                │
                ▼  (on cache miss or TTL expiry)
    ┌───────────────────────────────────┐
    │ NewsroomFetcher    (30 min TTL)   │
    │ StatusFetcher       (5 min)       │
    │ ResearchFetcher     (60 min)      │
    │ EngineeringFetcher  (60 min)      │
    │ ClaudeCodeDocsFetcher (60 min)    │
    │ ApiDocsFetcher        (60 min)    │
    │ ClaudeAppsDocsFetcher (60 min)    │
    │ SystemPromptsDocsFetcher (60 min) │
    │ SupportReleaseNotesFetcher (60m)  │
    │ EconomicIndexFetcher (120 min)    │
    │ Business/Trust filtered sources   │
    │ GitHubReleasesFetcher (30 min)    │
    │ GitHubOrgEventsFetcher (30 min)   │
    │ HackerNewsFetcher     (30 min)    │
    │ RedditFetcher         (60 min)    │
    └───────────────────────────────────┘
```

**Key design decisions:**

- **Stateless fetchers** — each fetcher is a pure async function; no state between calls.
  Caching is handled entirely by the retrieval layer.
- **Per-source TTLs** — each source has its own TTL. A stale source returns cached data
  while a background refresh runs; one broken source never blocks the others.
- **URL-based dedup** — items are deduplicated by canonical URL (fragments and `utm_*`
  params stripped, remaining params sorted). An article posted to both the newsroom and
  HN will appear once.
- **SQLite with WAL** — survives concurrent readers from multiple IDE sessions.
  The cache lives at `~/.cache/anthropic-news-mcp/cache.db`, not in the repo directory.

---

## Eval results

This server ships with a golden-prompt eval suite using `claude-haiku-4-5` as judge.

Each prompt is scored on three dimensions (0–2 each):

| Dimension | What it checks |
|-----------|---------------|
| Tool selection | Right tool + right parameters |
| Faithfulness | No hallucinated content |
| Helpfulness | Clear, useful to the user |

**Pass threshold: mean ≥ 5.0 / 6.0 across all prompts.**

See [`evals/`](./evals/) for the full methodology, golden Q&A pairs, and rubric.

To run the eval yourself:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install -e ".[eval]"
python evals/run_eval.py

# Deterministic seeded-cache eval data
python evals/run_eval.py --seed-cache
```

---

## Extending to other sources

The architecture is source-agnostic. Adding, say, an OpenAI changelog source is:

1. Create `src/anthropic_news_mcp/fetchers/openai_changelog.py` implementing `Fetcher`
2. Add a `SourceConfig` entry to `SOURCE_REGISTRY` in `config.py`

The `anthropic-news-mcp` name reflects v1 scope, not an architectural constraint.

---

## Development

```bash
# Clone and install with dev deps
git clone https://github.com/KeigoShimadaCC/anthropic-news-mcp
cd anthropic-news-mcp
uv pip install -e ".[dev]"

# Lint + format
ruff check .
ruff format .

# Type check
mypy --strict src/

# Tests (offline — no live HTTP calls)
pytest tests/ -v

# Live source-health audit (opt-in, not part of CI)
anthropic-news-audit
anthropic-news-audit --sources anthropic-status,anthropic-engineering
anthropic-news-audit --json evals/results/source_audit_$(date -u +%Y%m%dT%H%M%SZ).json
anthropic-news-audit --strict

# Run the server locally
python -m anthropic_news_mcp
```

---

## License

MIT — see [LICENSE](LICENSE).
