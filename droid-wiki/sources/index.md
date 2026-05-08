# Sources

The server tracks 17 sources, declared in `SOURCE_REGISTRY` in `src/anthropic_news_mcp/config.py`. Each source has its own fetcher class, TTL, default categories, and trust tier.

## Source registry at a glance

| Key | Source type | Tier | TTL | Categories |
|-----|-------------|------|-----|-----------|
| `anthropic-newsroom` | official | high | 30 min | models, research, policy, business |
| `anthropic-status` | official | high | 5 min | ops |
| `anthropic-research` | official | high | 60 min | research |
| `anthropic-engineering` | official | high | 60 min | engineering |
| `anthropic-docs-claude-code` | docs | high | 60 min | claude-code |
| `anthropic-docs-api` | docs | high | 60 min | models |
| `anthropic-docs-claude-apps` | docs | high | 60 min | models |
| `anthropic-docs-system-prompts` | docs | high | 60 min | policy |
| `anthropic-support-release-notes` | docs | high | 60 min | models |
| `anthropic-economic-index` | official | high | 120 min | economics, research |
| `anthropic-business-infrastructure` | official | high | 60 min | business |
| `anthropic-trust-policy` | official | high | 60 min | policy |
| `anthropic-github-releases` | github | medium | 30 min | claude-code, models |
| `anthropic-github-events` | github | medium | 30 min | claude-code |
| `anthropic-github-issues-prs` | github | medium | 30 min | claude-code, engineering |
| `hn-anthropic` | community | low | 30 min | community |
| `reddit-claude` | community | low | 60 min | community |

## By trust tier

The registry organizes sources into four trust tiers that drive dedup ranking:

| Tier | Source types | Sources |
|------|--------------|---------|
| [Official Anthropic](./official.md) | `OFFICIAL`, evidence `HIGH` | newsroom, status, research, engineering, economic-index, business-infrastructure, trust-policy |
| [Docs and release notes](./docs.md) | `DOCS`, evidence `HIGH` | docs-claude-code, docs-api, docs-claude-apps, docs-system-prompts, support-release-notes |
| [GitHub](./github.md) | `GITHUB`, evidence `MEDIUM` | github-releases, github-events, github-issues-prs |
| [Community](./community.md) | `COMMUNITY`, evidence `LOW` | hn-anthropic, reddit-claude |

When two items share a canonical URL, the higher-tier source's representative wins. See [retrieval](../systems/retrieval.md) for the full ranking tuple.

## Categories vs source keys

The 9-value `Category` enum (models, claude-code, research, policy, business, community, ops, engineering, economics) is orthogonal to source keys. A single item can belong to multiple categories. Filtering by category narrows the result set across all sources; filtering by source key narrows to specific sources.

For example, `get_recent_updates(categories=["models"])` will pull from the newsroom, API docs, Claude Apps docs, support release notes, and GitHub releases together.

## Adding a new source

Two steps:

1. Write a fetcher class in `src/anthropic_news_mcp/fetchers/<name>.py` subclassing `Fetcher` from `fetchers/base.py`. Set `source_key` as a class variable. Implement `async def fetch(self) -> list[NewsItem]`.
2. Add a `SourceConfig(...)` entry to `_build_registry()` in `src/anthropic_news_mcp/config.py` with the right TTL, default categories, source type, and evidence tier.

Position the new entry in the registry at the right place — earlier registry order wins ties in trust-ranked dedup.

For tests, freeze a real HTTP response into `tests/fixtures/<name>.<ext>` and add a parser test in `tests/test_fetchers/`.

See [Adding a new source](../how-to-contribute/development-workflow.md) for a worked example.
