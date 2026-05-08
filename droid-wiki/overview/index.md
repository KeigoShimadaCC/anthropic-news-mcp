# anthropic-news-mcp

`anthropic-news-mcp` is a Model Context Protocol (MCP) server that aggregates Anthropic-related signals — news, research, Claude Code changelogs, model releases, status incidents, GitHub activity, Hacker News, and Reddit — into a research-oriented MCP surface that LLM clients like Claude Desktop, Cursor, and ChatGPT can call directly.

The server is a single Python package (`src/anthropic_news_mcp/`) that exposes 15 tools, 7 resources, and 6 prompts over MCP stdio. Sources are fetched concurrently, normalized into a shared `NewsItem` schema, deduplicated by canonical URL, and cached in a local SQLite database. A second deployment mode exposes the same surface as a Streamable HTTP ASGI app with OIDC-validated bearer tokens.

## What it does

The server consolidates seventeen distinct sources spanning four trust tiers (official, docs, GitHub, community) and lets clients ask things like "what did Anthropic ship this week?" or "find evidence about RSP." The retrieval layer applies per-source TTLs so a stale source returns cached data while a background refresh runs, and one broken source never blocks the others. A research subsystem layers on top: it stores normalized full-page text and stable excerpt evidence, builds chronological topic timelines, persists local research sessions with notes and reports, and deterministically matches free-form claims against stored evidence.

## Quick links

- [Architecture](./architecture.md) — components, data flow, and design decisions
- [Getting started](./getting-started.md) — install, configure, and run the server
- [Glossary](./glossary.md) — domain vocabulary
- [API reference](../api/index.md) — full tool, resource, and prompt surface
- [Source registry](../sources/index.md) — the seventeen configured sources
- [How to contribute](../how-to-contribute/index.md) — workflow, testing, and conventions

## Tech stack

| Area | Choice |
|------|--------|
| Language | Python 3.11+ |
| MCP framework | `mcp>=1.27` (FastMCP) |
| HTTP | `httpx` async client with allowlisted host hook |
| HTML parsing | `selectolax` |
| Validation | `pydantic` v2 |
| Storage | SQLite (WAL mode + FTS5) |
| Remote transport (optional) | `starlette`, `uvicorn`, `PyJWT` |
| Tests | `pytest`, `pytest-asyncio` |
| Lint / type | `ruff`, `mypy --strict` |
| LLM eval (optional) | `anthropic` SDK with `claude-haiku-4-5` as judge |

## Project shape

| Section | Pages |
|---------|-------|
| [Apps](../apps/index.md) | stdio MCP server, remote ASGI deployment, source-audit CLI |
| [Systems](../systems/index.md) | retrieval, cache, fetchers, research, content extraction |
| [Sources](../sources/index.md) | the seventeen configured sources by trust tier |
| [Primitives](../primitives/index.md) | `NewsItem`, `SourceConfig`, evidence types |
| [API](../api/index.md) | MCP tools, resources, prompts |
| [Reference](../reference/index.md) | configuration, data models, dependencies |
