# anthropic-news-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that aggregates
Anthropic news, Claude Code changelogs, model releases, and community signals into a
research-oriented MCP surface for LLM clients like Claude Desktop and Cursor.

[![CI](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why

Anthropic ships fast. Signals land across official news, research, engineering, status,
docs release notes, support release notes, GitHub repos, Hacker News, and Reddit.
Tracking these manually is noise.

This MCP server consolidates them into MCP tools, resources, and prompts that any MCP
client can call. The data is cached locally in SQLite so repeat queries are sub-millisecond.
One failing source never blocks the others.

---

## What it gives Claude

| Tool | Purpose |
|------|---------|
| `ping` | Health check and server version |
| `list_sources` | Discover what sources are configured and their keys |
| `get_recent_updates` | The main feed — filterable by source, category, and date |
| `search_updates` | Keyword search over the local cache |
| `get_source_health` | Operational status per source (fetched when, how many items, any error) |
| `get_update_detail` | Fetch normalized full page text, stable excerpts, hashes, and provenance |
| `search_web_sources` | Search configured sources by query, date, category, type, importance, and tags |
| `get_timeline` | Build grouped chronological topic timelines with dedup clusters |
| `compare_updates` | Show new and changed items since a timestamp |
| `build_digest_context` | Return citation-ready evidence context for a client model to write a digest |
| `create_research_session` | Create a local SQLite research session |
| `save_research_note` | Save notes and follow-ups linked to evidence ids |
| `save_research_report` | Save generated report Markdown linked to evidence ids |
| `get_research_session` | Return session notes, reports, follow-ups, and linked evidence |
| `evaluate_claims` | Deterministically match claims to evidence excerpts and flag support gaps |

Most tools are read-only. Session/report/note tools persist local SQLite research state.
Returned item titles, summaries, authors, tags, URLs, and fetched page text are untrusted
external data fetched from the public web.

### Resources

| Resource | Purpose |
|----------|---------|
| `anthropic-news://sources` | Configured sources, categories, TTLs, and enabled status |
| `anthropic-news://health` | Cached source health without fetching remote sources |
| `anthropic-news://source/{source_key}/latest` | Latest cached items for one source |
| `anthropic-news://evidence/{evidence_id}` | Stored evidence excerpt by stable id |
| `anthropic-news://session/{session_id}` | Saved research session with notes, reports, and evidence |
| `anthropic-news://session/{session_id}/reports` | Saved reports for a session |
| `anthropic-news://timeline/{session_id}` | Timeline context for a session topic |

### Prompts

| Prompt | Purpose |
|--------|---------|
| `latest_update_digest` | Summarize the latest updates with citations |
| `source_health_report` | Diagnose stale or failing sources |
| `weekly_category_digest` | Build a weekly digest for one category |
| `generate_digest` | Ask the client model to write prose from `build_digest_context` |
| `verify_claims_against_evidence` | Ask the client model to explain `evaluate_claims` results |
| `research_session_brief` | Summarize a saved research session |

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
| `anthropic-github-issues-prs` | Recent issues and PRs from selected Anthropic/MCP repos |
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

Restart Claude Desktop. The MCP tools will appear automatically.

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
| `ANTHROPIC_NEWS_MCP_CACHE_DB` | No | Override the SQLite cache path. Defaults to `~/.cache/anthropic-news-mcp/cache.db`. |
| `ANTHROPIC_API_KEY` | Eval only | Required to run `evals/run_eval.py`. |

No API key is required for the official Anthropic, Claude Status, docs, or support sources.

### Streamable HTTP ASGI

For remote deployment, install the optional runtime dependencies:

```bash
pip install "anthropic-news-mcp[remote]"
```

Expose `anthropic_news_mcp.asgi:app` with any ASGI server:

```bash
export ANTHROPIC_NEWS_MCP_AUTH_ISSUER="https://issuer.example"
export ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE="anthropic-news"
export ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES="anthropic-news:read"
export ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS="mcp.example.com"
export ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS="https://client.example"
export ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL="https://mcp.example.com"
export ANTHROPIC_NEWS_MCP_RATE_LIMIT_PER_MINUTE="120"
export ANTHROPIC_NEWS_MCP_RATE_LIMIT_BURST="30"
uvicorn anthropic_news_mcp.asgi:app --host 0.0.0.0 --port 8000
```

The Streamable HTTP endpoint is `/mcp`. Remote mode is a resource server only: it validates
bearer JWTs from the configured OIDC issuer and does not implement an OAuth authorization
server. Startup fails unless issuer, audience, allowed hosts, and allowed origins are set.
Remote responses include `x-request-id`, request logs include structured request fields, and
the optional rate limit variables above control an in-memory token bucket. That limiter is
single-process only; use an edge gateway or shared store for distributed deployments.

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
        │  MCP stdio or Streamable HTTP (/mcp)
        ▼
 anthropic-news-mcp (FastMCP server)
        │
        ├─ ping
        ├─ list_sources
        ├─ get_recent_updates ──► async gather across all sources
        ├─ search_updates      ──► SQLite substring search
        ├─ research tools      ──► details, evidence, timelines, sessions
        ├─ get_source_health
        ├─ resources
        └─ prompts
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
    │ GitHubIssuesPullsFetcher (30 min) │
    │ HackerNewsFetcher     (30 min)    │
    │ RedditFetcher         (60 min)    │
    └───────────────────────────────────┘
```

**Key design decisions:**

- **Stateless fetchers** — each fetcher is a pure async function; no state between calls.
  Caching is handled entirely by the retrieval layer.
- **Per-source TTLs** — each source has its own TTL. A stale source returns cached data
  while a background refresh runs; one broken source never blocks the others.
- **Trust-ranked dedup** — items are deduplicated by canonical URL (fragments and `utm_*`
  params stripped, remaining params sorted). When duplicates exist, official/docs/GitHub
  sources outrank community discussion before recency and summary quality are considered.
- **SQLite with WAL** — supports concurrent readers in a single server instance.
  The cache lives at `~/.cache/anthropic-news-mcp/cache.db` by default and can be changed
  with `ANTHROPIC_NEWS_MCP_CACHE_DB`. Multi-instance shared storage is future work.
- **Evidence-first research** — detail, digest, timeline, and claim tools return evidence
  packages, excerpts, hashes, and support labels. They do not call an LLM or generate prose.
- **SQLite v2 research state** — full-content details, stable evidence excerpts, item
  history, sessions, notes, and reports are stored alongside the existing cache.
- **Untrusted source model** — fetched content is returned as data only. Clients should not
  execute or follow instructions contained in titles, summaries, tags, or linked pages.

---

## Eval results

This server ships with deterministic offline evals and an optional golden-prompt eval suite using `claude-haiku-4-5` as judge.

Each prompt is scored on three dimensions (0–2 each):

| Dimension | What it checks |
|-----------|---------------|
| Tool selection | Right tool + right parameters |
| Faithfulness | No hallucinated content |
| Helpfulness | Clear, useful to the user |

**Pass threshold: mean ≥ 5.0 / 6.0 across all prompts.**

See [`evals/`](./evals/) for the full methodology, golden Q&A pairs, and rubric.

To run the offline eval yourself:

```bash
pip install -e ".[dev]"
python evals/run_offline_eval.py
```

To run the optional paid LLM eval:

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
mypy --strict -p anthropic_news_mcp

# Tests (offline — no live HTTP calls)
pytest -q

# Deterministic offline evals
python evals/run_offline_eval.py

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
