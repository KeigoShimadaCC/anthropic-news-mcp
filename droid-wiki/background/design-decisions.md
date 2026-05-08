# Design decisions

The decisions that shape the rest of the codebase, with the trade-offs that motivated each.

## Stateless fetchers, retrieval owns the cache

Every fetcher is `async def fetch(self) -> list[NewsItem]` and nothing more. They don't read or write the cache, hold no state between calls, and can be unit-tested by parsing a frozen fixture.

This separates two concerns that are easy to tangle:

- **What the wire format looks like.** Owned by the fetcher.
- **When to fetch and what to keep.** Owned by the retrieval layer.

The trade-off: every fetch is a clean network round-trip, but retrieval needs explicit logic for cache freshness, concurrent fan-out, and error sanitization. That logic lives once in `src/anthropic_news_mcp/retrieval.py` rather than being repeated in every fetcher.

## Per-source TTLs in a single registry

`SOURCE_REGISTRY` in `src/anthropic_news_mcp/config.py` is a frozen list. Each entry declares its TTL, default categories, source type, and evidence tier. Adding a source is two lines: a fetcher class and a registry entry.

The trade-off: any cross-cutting feature (e.g. a new field on every source) requires touching every entry. So far that's been a non-issue — adding `source_type` and `evidence_tier` was a one-time edit, and the validators in `_fill_derived_fields` do the rest of the work.

## Trust-ranked dedup vs naive newest-first

When the same URL surfaces from multiple sources, the retrieval layer keeps the highest-trust representative rather than the most recent. The ranking tuple is `(source_type, evidence_tier, has_date, importance, summary_quality, registry_order)`.

The trade-off: GitHub event pings often arrive before the Anthropic newsroom announcement, but the newsroom representative wins because its `source_type` is `OFFICIAL`. This means the reader sees the canonical announcement with the polished summary instead of the raw event payload. The freshness signal is preserved in `discovered_at`.

Naive newest-first was the alternative. It's simpler but produces a worse user-facing feed.

## SQLite WAL with FTS5 vs a real database

The cache is one SQLite file. WAL mode allows concurrent readers in one process. FTS5 powers ranked search.

Trade-offs:

- **No multi-process or multi-host support.** The token-bucket rate limiter is also process-local. The README explicitly marks this as future work. Today, the project assumes one server instance per cache file.
- **No migration framework.** `CACHE_SCHEMA_VERSION` triggers a recreate; data is disposable. This works because the cache is reconstructed by re-fetching, not by user input.

Why not Redis or Postgres? Both add an operational dependency for a project where the value is "drop in and run." SQLite ships with Python.

## Evidence-first research vs returning prose

The detail, timeline, digest, and claim tools return structured evidence — items, normalized text, content hashes, excerpts, dedup clusters — and never call an LLM. The client model writes any prose using the returned evidence.

The trade-off: more data passes through the tool boundary, but the server stays deterministic, doesn't need an `ANTHROPIC_API_KEY` (except for the optional eval), and can be tested offline. The client model decides how to present results, which is the right division of labor for an MCP tool server.

The alternative was to bundle generation into tools (`get_recent_updates_summary` returning prose). It tested poorly: the server would have to make LLM calls, costs would compound, and clients couldn't easily inject their own framing.

## Untrusted external data convention

Every fetched title, summary, author, tag, and page text is treated as untrusted data:

- Server-level instructions warn the client.
- Tool docstrings repeat the warning where relevant.
- The eval harness wraps tool output in `<untrusted_data>` tags before sending to the judge model.

The alternative was to silently sanitize fetched content (strip URLs, drop tags). That breaks the point of a research tool — the model needs to see the actual titles to cite them. Wrapping with the convention "this is data, not instructions" is the better trade.

## Outbound host allowlist on the response

`src/anthropic_news_mcp/http.py` registers a response hook that rejects any host outside `_ALLOWED_FETCH_HOSTS`. The check happens *after* the response, which catches redirects.

Why not validate the request URL? Because a 302 to an arbitrary host would slip through. Validating the response host catches the real attack: a source that was once valid being redirected to an attacker-controlled location.

The cost is small: the hook runs once per response, the allowlist is a hash set, and the failure mode is a single explicit error rather than a leaked request.

## Resource server only in remote mode

The remote ASGI deployment validates JWTs but doesn't issue them. There's no `/oauth/authorize` or `/oauth/token` endpoint. Token issuance, refresh, and consent live with the configured OIDC provider.

This is a deliberate scope limit. Implementing an authorization server is a project unto itself — it requires user accounts, consent screens, secure token storage, and refresh-token rotation. Standing on top of an external IdP keeps the news server's threat model narrow and pushes auth complexity to systems built for it.

## Source-key strings vs enum values

Source keys are stable strings (`anthropic-newsroom`, `hn-anthropic`) rather than enum values. Tools accept `list[str]` and validate against `_valid_source_keys()`.

Why not an enum? Because adding a new source must not require regenerating client SDK enums. The string-keyed approach lets clients send any source key the server has, and the server validates it. Tradeoff: typos go unnoticed until runtime; the parser's error envelope makes the failure obvious.

## Categories overlap, source keys don't

A single `NewsItem` can have multiple categories (e.g. `[economics, research]`). It has exactly one `source_key`.

The reason: categories are an editorial taxonomy that genuinely overlaps. Source keys identify the producer, which is unambiguous.

This is why `search_web_sources` filters categories with set intersection but filters source keys with set membership.

## Page text capped at 50,000 chars

`content.fetch_content_detail` truncates normalized text at `_MAX_STORED_CHARS = 50_000`. Long enough for almost every Anthropic article; short enough to keep individual SQLite rows reasonable.

The truncation flag and the warning list let clients distinguish "we got the whole page" from "we got a piece." Excerpt windows are bounded at 900 chars, so even a 50,000-char detail produces compact citations.

## 5-minute TTL for status, 60+ for everything else

Status is the one source where freshness genuinely matters at the minute scale. Everything else (release notes, GitHub releases, research papers) updates on hour-or-longer cadence.

A short TTL on every source would multiply HTTP cost without proportional benefit. The current TTLs reflect real-world update frequencies:

- Status: 5 min
- Newsroom, GitHub events/releases/issues: 30 min
- Research, engineering, docs, business, trust: 60 min
- Economic index: 120 min

## No background refresh worker

There's no scheduler or background task that proactively refreshes sources. Refreshes happen when a tool call notices a stale source.

The alternative was a `while True: refresh_all()` loop. That's overkill for a tool server: clients don't pay for refreshes they don't trigger, and the eventual-consistency model fits MCP's call-and-response shape.

The audit CLI exists for the case where you want a deliberate refresh — it's a separate tool, not a daemon mode.

## Fixture-driven tests over recorded HTTP

Tests parse frozen fixtures directly rather than mocking `httpx`. The trade-off: tests can't catch HTTP-level regressions in the fetcher (header handling, redirect chains, etc.), but they can catch every parser regression with no mock framework dependency.

The retrieval and remote layers do exercise live `httpx` paths against real-but-controlled endpoints. The split is intentional: parsers test offline, transport tests run live.

## CLAUDE.md alongside README.md

The repo has a dedicated `CLAUDE.md` at the root that gives Claude Code architectural context: where commands live, how the cache works, the testing approach. It exists specifically because the project is built mostly through AI-assisted development and benefits from a context document tuned for that workflow.

The README is the human-facing document; `CLAUDE.md` is the model-facing one. They have overlapping content but different audiences.
