# How to Make a Good MCP

This report explains what makes a Model Context Protocol server good in practice. A good
MCP is not just a server that responds to tool calls. It is a reliable product interface
between an AI client and a real system: easy for a model to use correctly, hard to misuse,
clear about trust boundaries, observable when things fail, and stable enough for clients to
build workflows around it.

The examples are grounded in this repository, `anthropic-news-mcp`, which aggregates
Anthropic-related updates and now exposes research-oriented evidence, timeline, session,
and claim-evaluation workflows.

References:

- MCP base protocol overview: https://modelcontextprotocol.io/specification/2025-06-18/basic/index
- MCP server primitives: https://modelcontextprotocol.io/specification/2025-06-18/server/index
- MCP tools: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP resources: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- MCP prompts: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
- MCP transports: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP authorization: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- MCP security best practices: https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices

## Executive Summary

A good MCP server is a narrow, typed, well-documented bridge from an AI client to a domain.
It should expose the right MCP primitives, validate inputs aggressively, return structured
outputs, document what data is trusted and untrusted, handle partial failures, and include
tests that protect the contract clients depend on.

Good MCP design is not "wrap every internal function as a tool." A good server decides what
belongs in each primitive:

| MCP primitive | Who controls it | Best use |
|---|---:|---|
| Tools | Model-controlled | Searches, actions, retrieval, calculations, and operations the model may invoke |
| Resources | Application-controlled | Read-only context the client may attach or display |
| Prompts | User-controlled | Reusable workflows or task templates users intentionally choose |

This repo demonstrates that separation:

- Tools perform retrieval, search, details, timelines, persistence, and evidence checks.
- Resources expose read-only source, health, evidence, session, report, and timeline
  context.
- Prompts guide common user workflows such as digests, health reports, claim review, and
  research-session summaries.
- Fetchers, storage, content extraction, and research state are kept behind the MCP surface.

The core lesson: an MCP server is a product interface, not a dump of internal implementation
details.

## What a Good MCP Is

A good MCP server has six properties.

First, it has a clear domain boundary. It should do one job well. This repository's job is
not "browse the internet"; it is "aggregate Anthropic news, model releases, Claude Code
changelogs, operational status, official docs, GitHub activity, and community signals for
research workflows." That scope is encoded in the source registry and fetchers.

Second, it exposes a minimal but complete interface. The client can discover sources, fetch
recent updates, search cached and upstream-like source data, fetch full article details,
build timelines, compare changes, persist a research session, and evaluate claims against
evidence. The server does not expose every parser or storage operation as a public tool.

Third, it returns structured, predictable data. The server uses typed models for news items,
source health, details, evidence excerpts, sessions, reports, timelines, and claim
evaluations. Models are better at using stable fields than parsing loose prose.

Fourth, it is safe by default. The server declares fetched content as untrusted external data,
uses tool annotations, bounds user inputs, rejects blank or invalid filters, redacts secrets,
and protects remote HTTP mode with JWT, Host, and Origin checks.

Fifth, it handles reality. External sources fail. Some content is stale. Some pages cannot be
extracted. Some claims have weak evidence. A good MCP returns partial results, warnings,
health information, timestamps, hashes, provenance, and confidence labels instead of hiding
uncertainty.

Sixth, it can be verified. This repo includes contract tests, cache tests, content tests,
research tests, fetcher tests, remote auth tests, and quality gates. MCP servers are
interfaces; interface drift breaks clients even when internal code still runs.

## Current Repo Surface

As of this report, `anthropic-news-mcp` exposes these tools:

| Tool | Purpose |
|---|---|
| `ping` | Health check and server version |
| `list_sources` | Discover configured source keys and metadata |
| `get_recent_updates` | Main feed filtered by source, category, and date |
| `search_updates` | Keyword search over the local cache |
| `get_source_health` | Operational status per source |
| `get_update_detail` | Fetch normalized full page text, excerpts, hash, URL, and retrieval timestamp |
| `search_web_sources` | Search configured sources with query, date, source type, category, importance, and tag filters |
| `get_timeline` | Group topic-related updates chronologically with dedup clusters |
| `compare_updates` | Show what is new, changed, or disappeared since a timestamp |
| `build_digest_context` | Return citation-ready evidence for a client model to write a digest |
| `create_research_session` | Create a local SQLite research session |
| `save_research_note` | Save user notes and follow-ups linked to evidence ids |
| `save_research_report` | Save generated report Markdown linked to evidence ids |
| `get_research_session` | Return saved session state, notes, reports, follow-ups, and linked evidence |
| `evaluate_claims` | Match answer claims against retrieved evidence and flag support gaps |

It exposes these resources:

| Resource | Purpose |
|---|---|
| `anthropic-news://sources` | Configured sources, categories, TTLs, evidence tiers, and enabled status |
| `anthropic-news://health` | Cached source health without forcing a fresh fetch |
| `anthropic-news://source/{source_key}/latest` | Latest cached items for one source |
| `anthropic-news://evidence/{evidence_id}` | Stored evidence excerpt by stable id |
| `anthropic-news://session/{session_id}` | Saved research session with notes, reports, and evidence |
| `anthropic-news://session/{session_id}/reports` | Saved reports for a session |
| `anthropic-news://timeline/{session_id}` | Timeline context for a saved research session |

It exposes these prompts:

| Prompt | Purpose |
|---|---|
| `latest_update_digest` | Summarize latest updates with citations |
| `source_health_report` | Diagnose stale or failing sources |
| `weekly_category_digest` | Build a weekly digest for one category |
| `generate_digest` | Ask the client model to write prose from `build_digest_context` |
| `verify_claims_against_evidence` | Ask the client model to explain `evaluate_claims` results |
| `research_session_brief` | Summarize a saved research session |

This is a much stronger interface for an AI research bot than a simple list/search server.
It supports retrieval, provenance, citation material, timelines, saved research state, and
claim checking.

## Recommended Structure

A production MCP server should separate protocol surface, domain logic, models, external I/O,
storage, configuration, and tests.

This repo uses that pattern:

```text
src/anthropic_news_mcp/
  server.py              # MCP tools, resources, prompts, and server instructions
  asgi.py                # ASGI entrypoint for Streamable HTTP mode
  remote.py              # JWT validation, Host/Origin protection, resource metadata
  models.py              # Pydantic domain models returned by tools/resources
  config.py              # Source registry, categories, source types, evidence tiers
  retrieval.py           # Aggregation, cache orchestration, dedup, filtering
  cache.py               # SQLite cache, health, item history, research persistence
  content.py             # Full-page extraction, normalized text, hashes, excerpts
  research.py            # Timelines, digests, sessions, reports, claim evaluation
  http.py                # Shared HTTP client and outbound host validation
  audit.py               # Operational source-health audit CLI
  fetchers/
    base.py              # Fetcher protocol/base interface
    newsroom.py          # Official source parsers
    official.py
    docs_api.py
    docs_claude_code.py
    github_events.py
    github_releases.py
    github_issues.py
    hackernews.py
    reddit.py
tests/
  test_server.py         # MCP contract tests
  test_retrieval.py      # Dedup/filter/cache orchestration tests
  test_cache.py          # SQLite behavior
  test_content.py        # Content extraction, excerpts, hashes
  test_research.py       # Sessions, timelines, digests, claim evaluation
  test_http.py           # HTTP safety behavior
  test_remote.py         # ASGI/auth/Host/Origin tests
  test_fetchers/         # Source parser tests
```

The important pattern is that `server.py` stays thin. It should validate MCP inputs, call
domain services, and shape responses. It should not parse HTML, implement retry policies,
contain every source-specific endpoint, or own storage details.

## Tool Design

Tools are model-controlled. The model may decide to call them without the user explicitly
choosing each call. That makes the contract important.

A good MCP tool has:

- A clear name that describes the operation.
- A narrow purpose.
- A bounded input schema.
- Friendly validation errors.
- Structured output.
- Clear side-effect annotations.
- Stable ids for anything that may be cited, fetched, or revisited.
- Warnings when results are partial, stale, truncated, or low confidence.

This repo applies those rules in concrete ways.

`list_sources` prevents models from guessing source keys. It returns source metadata such as
category, source type, TTL, evidence tier, and enabled status.

`get_recent_updates` is the canonical feed tool. It supports `source`, `category`, `since`,
and `limit`, and rejects invalid categories, source keys, malformed dates, date-only
timestamps, negative limits, and oversized limits.

`search_updates` is intentionally cache-oriented. It rejects blank queries and self-warms
the cache on cold start so the first search can still return useful results.

`search_web_sources` is the richer research search tool. It combines query, sources,
categories, source types, importance, tags, date range, and limit. This is much better for a
research bot than forcing the model to call several narrow tools and merge results itself.

`get_update_detail` returns full normalized page text when available, plus stable excerpts,
retrieved timestamp, source URL, content hash, warnings, and truncation state. That makes it
usable for citations and later claim checks.

`evaluate_claims` deliberately does deterministic lexical matching rather than pretending to
prove truth. It returns support labels such as `strong_support`, `weak_support`,
`unsupported`, and `needs_review`. That is honest behavior for an evidence-checking tool.

## Resources

Resources are application-controlled. They are best for stable context the client can attach
or display without the model deciding to perform an operation.

This repo uses resources well:

- Source catalog: `anthropic-news://sources`
- Cached health: `anthropic-news://health`
- Latest items for one source: `anthropic-news://source/{source_key}/latest`
- Evidence excerpt lookup: `anthropic-news://evidence/{evidence_id}`
- Saved session lookup: `anthropic-news://session/{session_id}`
- Saved report lookup: `anthropic-news://session/{session_id}/reports`
- Timeline lookup: `anthropic-news://timeline/{session_id}`

The distinction matters. A source list is context. A full refresh across remote sources is
an operation. A saved report is context. Creating or saving a report is an operation.

## Prompts

Prompts are user-controlled reusable workflows. They should encode how to use tools and
resources, but they should not hide evidence or make unsupported claims.

This repo's prompts are useful because they map to real workflows:

- `latest_update_digest` helps write a current update summary.
- `source_health_report` helps diagnose source reliability.
- `weekly_category_digest` narrows a digest by category and time.
- `generate_digest` tells the client model to use `build_digest_context` and cite evidence.
- `verify_claims_against_evidence` turns claim-evaluation output into a readable review.
- `research_session_brief` summarizes saved notes, reports, follow-ups, and evidence.

A good prompt should tell the model what evidence to use and what uncertainty to preserve.
It should not ask the model to invent missing citations.

## Evidence and Citations

For an AI research bot, basic summaries are not enough. The bot needs evidence it can cite.

This repo adds evidence support through:

- Full-page content retrieval in `content.py`.
- Normalized page text, so HTML noise is removed before the model sees content.
- Stable evidence excerpts, so cited spans can be revisited.
- Source URLs, so a human can inspect the original.
- Retrieved timestamps, so a report can say when the evidence was collected.
- Content hashes, so changes can be detected.
- Evidence ids, so notes, reports, timelines, and claim evaluations can link to the same
  stored material.

This structure is better than returning a paragraph of prose because it lets the client model
separate "what the server retrieved" from "what the model concluded."

## Query Planning

A research bot needs more than keyword search. It needs to combine constraints.

This repo supports query planning through `search_web_sources`:

- `query` for text matching.
- `sources` for exact source keys.
- `categories` for product/research/policy/community style filtering.
- `source_types` for official, community, GitHub, docs, status, or similar provenance.
- `importance` for higher-signal items.
- `tags` for topic-level filtering.
- `since` and `until` for date range.
- `limit` for bounded result size.
- `refresh` for explicit upstream/cache refresh behavior.

That means the model can ask focused questions such as "official policy updates about model
safety since last month" without downloading unrelated Reddit or Hacker News results.

## Synthesis Workflows

Good MCP servers do not need to run an LLM internally. They should return the right context
for the client model to synthesize.

This repo follows an evidence-first pattern:

- `get_timeline` groups updates chronologically and clusters related items.
- `compare_updates` identifies what changed since a timestamp or previous run.
- `build_digest_context` returns citation-ready evidence but does not write the final prose.
- `generate_digest` is a prompt-backed workflow that tells the client model how to write from
  the evidence.

This is a good division of responsibility. The MCP server handles retrieval, normalization,
deduplication, persistence, and provenance. The client model handles language synthesis.

## Persistence

Some MCP tools should be read-only. Some should intentionally write state. The important
thing is to make side effects explicit.

This repo is mostly read-oriented, but it now has local research persistence:

- `create_research_session` stores a session topic, filters, and follow-up state.
- `save_research_note` stores notes linked to evidence ids.
- `save_research_report` stores generated Markdown reports linked to evidence ids.
- `get_research_session` retrieves the saved research state.

The persistence layer is SQLite. The cache path defaults to
`~/.cache/anthropic-news-mcp/cache.db` and can be overridden with
`ANTHROPIC_NEWS_MCP_CACHE_DB`.

The schema stores both retrieval cache and research state, including full-content details,
evidence excerpts, item history, research sessions, notes, and reports. SQLite WAL mode is
appropriate for a single ASGI instance with persistent local storage. Multi-instance shared
storage should be treated as future work unless the storage layer is replaced with a shared
database.

## Trust and Security

A good MCP has an explicit trust model.

In this repo, titles, summaries, authors, tags, URLs, Reddit posts, Hacker News comments,
GitHub issues, release notes, docs pages, and full fetched page text are untrusted external
data. They must be returned as data, not followed as instructions.

Good security practices shown here:

- Server instructions warn clients that fetched content is untrusted.
- Remote mode requires OIDC/JWT issuer and audience.
- Remote mode can require scopes.
- Remote mode validates `Host` and `Origin`.
- Startup refuses insecure remote configuration.
- Secrets in URLs, headers, tokens, and query strings are redacted in errors/logs.
- Outbound redirects and final hosts are checked.
- Date parsing rejects unsafe date-only or naive timestamp inputs.
- Blank searches and negative limits are rejected.

For remote deployment, this repo exposes `anthropic_news_mcp.asgi:app` and serves Streamable
HTTP at `/mcp`. It is a resource server only; it validates bearer JWTs but does not implement
an OAuth authorization server.

## Reliability

External data sources fail constantly. A good MCP should make those failures understandable.

This repo does that with:

- Per-source TTLs.
- Source health state.
- Partial result behavior.
- Cached fallback behavior.
- URL-based deduplication.
- Content extraction warnings.
- Stale-source reporting.
- Cold-cache search warmup.

`get_source_health` is especially important. It lets a model say "the status source is fresh,
but Reddit is stale" instead of presenting incomplete results as complete.

## What This Repo Gets Right

This repo is a strong MCP example because it has:

- A focused domain.
- A clear source registry.
- Structured Pydantic models.
- Thin MCP surface in `server.py`.
- Separate fetchers for source-specific parsing.
- SQLite cache with configurable path.
- Research-specific content extraction and evidence persistence.
- Tool annotations and structured outputs.
- Resources for cached context.
- Prompts for repeatable workflows.
- Remote ASGI support with JWT, Host, and Origin checks.
- Tests for server contracts, retrieval, cache, content, research, remote auth, and fetchers.
- Documentation that describes local stdio, remote HTTP, trust boundaries, and single-instance
  SQLite behavior.

## Where to Keep Improving

Even a good MCP has room to mature. For this repo, useful next improvements would be:

- Add literal `search` and `fetch` adapter tools for clients that expect those names.
- Add richer semantic claim matching in addition to deterministic lexical matching.
- Add a shared database option for multi-instance remote deployments.
- Add more official source coverage, especially docs diffs, release notes, support docs, and
  status history.
- Add source-specific quality scores that can evolve from static `evidence_tier` metadata.
- Add export formats for saved sessions and reports.
- Add pagination for very large sessions or result sets.

## Good MCP Checklist

Use this checklist when designing or reviewing an MCP server:

- The domain is clear in one sentence.
- Every tool has a narrow purpose and bounded inputs.
- Inputs reject invalid keys, blank strings, unsafe timestamps, and unbounded limits.
- Outputs are structured, stable, and documented.
- Tool annotations accurately describe read/write behavior and open-world access.
- Resources expose context, not operations.
- Prompts encode workflows without hiding evidence.
- External content is explicitly treated as untrusted.
- Returned evidence includes URLs, timestamps, ids, and enough text to cite.
- Side-effect tools are clearly named and documented.
- Partial failures return warnings and health information.
- Remote mode uses TLS, bearer auth, issuer/audience checks, scopes, Host validation, and
  Origin validation.
- Secrets are redacted from logs and errors.
- Storage behavior is documented, including single-instance assumptions.
- Contract tests verify tool names, schemas, annotations, resources, prompts, and docs.
- CI runs linting, formatting, type checking, and tests.

## Anti-Patterns

Avoid these MCP design mistakes:

- Exposing every internal function as a tool.
- Returning only prose when structured fields would work.
- Letting the model guess source keys or ids.
- Hiding source freshness and partial failures.
- Treating external fetched text as trusted instructions.
- Making tools unbounded by default.
- Using prompts as a substitute for retrieval or validation.
- Adding write actions without clear names and annotations.
- Relying on local SQLite for multiple remote instances without documenting the limitation.
- Claiming "verified" when the tool only found weak lexical overlap.

## Bottom Line

A good MCP turns a messy system into a small, reliable, typed interface for AI clients.
For a research bot, that means more than search: it needs evidence, provenance, citations,
timelines, change tracking, saved state, and claim evaluation.

`anthropic-news-mcp` now demonstrates those patterns well. It keeps retrieval and evidence
handling inside the server, keeps synthesis in the client model, and exposes enough structure
for Claude, ChatGPT, Codex, or another MCP client to produce grounded research instead of
unsupported summaries.
