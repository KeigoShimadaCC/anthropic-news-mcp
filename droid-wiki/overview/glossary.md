# Glossary

Project-specific terms used throughout the codebase and this wiki.

## Core types

**`NewsItem`** — The canonical data type for a single news, changelog, release, or community item. Defined in `src/anthropic_news_mcp/models.py`. Every fetcher returns `list[NewsItem]`. ID format is `<source-prefix>-<stable-hash-or-native-id>`.

**`SourceConfig`** — Dataclass describing one source: its key, fetcher class, TTL, default categories, source type, and evidence tier. The full list lives in `SOURCE_REGISTRY` in `src/anthropic_news_mcp/config.py`.

**`SourceHealth`** — Operational record per source: status, last-fetch time, expiry, item count, and any sanitized error.

**`ContentDetail`** — Normalized full-page text for one item, with content hash and warnings. Produced by `content.fetch_content_detail`.

**`EvidenceExcerpt`** — A stable, content-hashed text window inside a `ContentDetail`. Used by digest, timeline, and claim-evaluation tools to provide citable evidence to client models.

**`DedupCluster`** — A group of `NewsItem`s sharing a canonical URL, with a chosen representative. Built in topic timelines.

## Categories and tiers

**Category** — An enum of nine logical buckets used for filtering: `models`, `claude-code`, `research`, `policy`, `business`, `community`, `ops`, `engineering`, `economics`. A single item can belong to multiple categories. Defined in `src/anthropic_news_mcp/models.py`.

**`SourceType`** — Provenance class: `official`, `docs`, `github`, `community`. Used for trust ranking during dedup and for filtering in `search_web_sources`.

**`EvidenceTier`** — Trust quality: `high`, `medium`, `low`. Official and docs sources are high; GitHub is medium; HN and Reddit are low.

**`SourceStatus`** — Cache state per source: `live` (just fetched), `cache` (served from a fresh snapshot), `stale` (served despite expiry because a refresh failed), `down` (never fetched and last refresh failed), `not_fetched` (never observed).

**`DateConfidence`** — Quality of the `published_at` field: `exact` (parsed from source), `inferred` (derived from a section heading), `unknown` (no usable date).

**`ClaimSupport`** — Output of `evaluate_claims`: `strong_support`, `weak_support`, `unsupported`, `needs_review`.

## Source keys

The 17 source keys are registered in `SOURCE_REGISTRY`. They're stable identifiers used throughout the API:

- `anthropic-newsroom`, `anthropic-status`, `anthropic-research`, `anthropic-engineering`
- `anthropic-docs-claude-code`, `anthropic-docs-api`, `anthropic-docs-claude-apps`, `anthropic-docs-system-prompts`
- `anthropic-support-release-notes`, `anthropic-economic-index`
- `anthropic-business-infrastructure`, `anthropic-trust-policy`
- `anthropic-github-releases`, `anthropic-github-events`, `anthropic-github-issues-prs`
- `hn-anthropic`, `reddit-claude`

See [the source registry](../sources/index.md) for full descriptions.

## Concepts

**Canonical URL** — A URL with the fragment dropped, `utm_*` query parameters stripped, and remaining params decoded and sorted. Used as the dedup key. Implementation: `_canonicalize_url` in `src/anthropic_news_mcp/retrieval.py`.

**Trust-ranked dedup** — When two items share a canonical URL, the representative is chosen by a tuple ranking source type, evidence tier, presence of `published_at`, importance, summary length, and registry order. Implementation: `_representative_key` in `src/anthropic_news_mcp/retrieval.py`.

**TTL (time-to-live)** — Per-source freshness window in seconds, defined in `SourceConfig.ttl_seconds`. Status sources have a 5-minute TTL; research and engineering have 60 minutes; the economic index is 120 minutes.

**Evidence-first** — A design principle: detail, timeline, digest, and claim tools return structured evidence (items, excerpts, hashes, source provenance) and never invoke an LLM themselves. The client model writes any prose using the returned evidence.

**Untrusted external data** — Fetched titles, summaries, authors, tags, and page text. The server-level instructions and tool descriptions both warn clients to treat these as data, not as instructions.

**FTS5** — SQLite's built-in full-text search extension. The cache builds an `items_fts` virtual table over title, summary, tags, source key, source type, and evidence tier; ranked search uses BM25 with weighted columns. See `cache.search_items` in `src/anthropic_news_mcp/cache.py`.

**Streamable HTTP** — The MCP transport used by the remote ASGI deployment. Mounts at `/mcp`. Configured in `src/anthropic_news_mcp/remote.py`.

**Resource server (OAuth)** — In remote mode, the server only validates JWT bearer tokens issued by an external OIDC provider. It does not implement an OAuth authorization server itself.

## Internal acronyms

**MCP** — Model Context Protocol. The standard this server speaks. See [modelcontextprotocol.io](https://modelcontextprotocol.io).

**RSP** — Responsible Scaling Policy. An Anthropic policy term that surfaces in `Trust & Policy` source filtering.

**WAL** — Write-Ahead Logging. The SQLite journal mode used by the cache to support concurrent readers.

**JWKS** — JSON Web Key Set. The remote-mode JWT verifier fetches signing keys from `${issuer}/.well-known/jwks.json`.

**TTL** — Time-to-live. Per-source cache freshness window.
