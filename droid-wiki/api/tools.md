# Tools

The 15 MCP tools defined in `src/anthropic_news_mcp/server.py`. Tools are grouped by purpose: news retrieval, research, and session management.

## News retrieval

### `ping`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def ping() -> dict[str, str]
```

Health check. Returns `{"status": "ok", "server": "anthropic-news-mcp", "version": "..."}`.

### `list_sources`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def list_sources() -> dict[str, object]
```

Lists every entry in `SOURCE_REGISTRY` with key, description, enabled flag, default categories, TTL seconds, source type, and evidence tier.

### `get_recent_updates`

```python
async def get_recent_updates(
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    since: str | None = None,
    limit: int = 20,  # max 100
) -> dict[str, object]
```

The main feed tool. Aggregates across all enabled sources, applies trust-ranked dedup, filters by categories and `since`, returns top-N by `sort_at` desc. Returns `{"items": [...], "sources": [...health...]}`.

`since` must be timezone-aware ISO 8601 (e.g. `2026-04-01T00:00:00Z`).

### `search_updates`

```python
async def search_updates(query: str, limit: int = 10) -> dict[str, object]
```

Ranked FTS5 search over the cached items. Warms the cache on first call. Returns `{"items": [...], "query": "..."}`.

### `get_source_health`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def get_source_health() -> dict[str, object]
```

Returns operational status per source. Sources never fetched have status `not_fetched` with `error: "Never fetched"`.

## Research

### `get_update_detail`

```python
async def get_update_detail(
    id: str,
    refresh: bool = False,
    max_chars: int = 12000,  # max 40000
    excerpt_query: str | None = None,
) -> dict[str, object]
```

Returns one item with normalized full-page text (truncated to `max_chars`), evidence excerpts, content hash, and provenance. If `refresh=True` or no detail is cached, fetches the page live. `excerpt_query` focuses the excerpt window selection.

### `search_web_sources`

```python
async def search_web_sources(
    query: str,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    source_types: list[str] | None = None,
    importance: list[int] | None = None,
    tags: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 20,  # max 100
    refresh: bool = False,
) -> dict[str, object]
```

Filtered search across cached items. With `refresh=True`, fetches full content for the first 20 missing items concurrently. Returns items plus evidence excerpts for the top 10 matches.

### `get_timeline`

```python
async def get_timeline(
    topic: str,
    since: str,
    until: str | None = None,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    source_types: list[str] | None = None,
    limit: int = 100,  # max 200
) -> dict[str, object]
```

Builds a chronological topic timeline grouped by date. `since` is required (no implicit default). Returns daily groups with items and dedup clusters, plus a `signals_by_source_type` breakdown.

### `compare_updates`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def compare_updates(since: str | None = None, limit: int = 100) -> dict[str, object]  # max 200
```

Diffs the cache against `item_history`. Returns `{since, new_items, changed_items, disappeared_items}`.

### `build_digest_context`

```python
async def build_digest_context(
    topic: str | None = None,
    since: str | None = None,
    until: str | None = None,
    categories: list[str] | None = None,
    sources: list[str] | None = None,
    limit: int = 50,  # max 100
) -> dict[str, object]
```

Wraps `get_timeline` with digest-writing instructions. The instructions block tells the client model to separate official/docs/GitHub/community signals and to treat evidence text as untrusted external data. Returns `{topic, instructions, timeline}`.

When `since` is omitted, defaults to "30 days ago" via `datetime.now(tz=UTC) - timedelta(days=30)`.

### `evaluate_claims`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def evaluate_claims(
    claims: list[str],
    evidence_ids: list[str] | None = None,
    session_id: str | None = None,
    query: str | None = None,
    limit: int = 10,  # max 50
) -> dict[str, object]
```

Deterministic term-overlap match between claims and evidence excerpts. Each claim gets a `ClaimSupport` label and a ranked list of supporting excerpts. No LLM call. See [Research system](../systems/research.md) for the algorithm.

## Sessions

### `create_research_session`

```python
@mcp.tool(annotations=LOCAL_WRITE, structured_output=True)
async def create_research_session(
    title: str,
    topic: str | None = None,
    filters: dict[str, object] | None = None,
) -> dict[str, object]
```

Creates a new local research session. `filters` is opaque to the server — clients can store any structured filter set.

### `save_research_note`

```python
@mcp.tool(annotations=LOCAL_WRITE, structured_output=True)
async def save_research_note(
    session_id: str,
    text: str,
    evidence_ids: list[str] | None = None,
    follow_up: bool = False,
) -> dict[str, object]
```

Saves a note linked to optional evidence excerpt IDs. `follow_up=True` flags the note as an open question.

### `save_research_report`

```python
@mcp.tool(annotations=LOCAL_WRITE, structured_output=True)
async def save_research_report(
    session_id: str,
    title: str,
    markdown: str,
    evidence_ids: list[str] | None = None,
) -> dict[str, object]
```

Saves a model-generated report (markdown body) against a session.

### `get_research_session`

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def get_research_session(session_id: str) -> dict[str, object]
```

Returns the session, all notes, all reports, and the union of evidence excerpts cited by any of them.

## Argument validation

All tools that accept structured input validate via the helpers documented in [Patterns and conventions](../how-to-contribute/patterns-and-conventions.md):

- `_parse_sources` — checks every key is in `SOURCE_REGISTRY`
- `_parse_categories` — coerces to `Category` enum
- `_parse_source_types` — coerces to `SourceType` enum
- `_parse_importance` — checks values are in `{1, 2, 3}`
- `_parse_since` — parses TZ-aware ISO 8601
- `_validate_time_range` — `since < until`
- `_parse_limit` — bounds-checks against `default_max`

Validation failures return the error envelope documented in [API overview](./index.md).

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/server.py` | All tool definitions |
| `src/anthropic_news_mcp/retrieval.py` | Implementation backing news retrieval tools |
| `src/anthropic_news_mcp/research.py` | Implementation backing research and session tools |
