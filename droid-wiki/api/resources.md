# Resources

7 MCP resources expose cached state without triggering live HTTP. All defined in `src/anthropic_news_mcp/server.py`.

## `anthropic-news://sources`

Returns the same payload as `list_sources`. Useful for clients that prefer resource discovery over tool calls.

```python
@mcp.resource(
    "anthropic-news://sources",
    name="sources",
    description="Configured Anthropic news sources and categories.",
    mime_type="application/json",
)
```

## `anthropic-news://health`

Returns cached source health. Unlike `get_source_health`, this resource never triggers a refresh.

## `anthropic-news://source/{source_key}/latest`

Latest 20 cached items for one source, plus the source's health record. The handler validates `source_key` against `_valid_source_keys()` and returns an error envelope on unknown keys.

## `anthropic-news://evidence/{evidence_id}`

One stored evidence excerpt by stable ID. Returns the full `EvidenceExcerpt` shape including text, char offsets, content hash, and provenance.

## `anthropic-news://session/{session_id}`

Full research session payload: session, notes, reports, and the union of cited evidence excerpts.

## `anthropic-news://session/{session_id}/reports`

Just the reports for a session. Equivalent to `get_research_session` filtered to the `reports` key.

## `anthropic-news://timeline/{session_id}`

Builds a timeline for the session's topic. Requires the session to have a `topic` field set; otherwise returns an error envelope.

The timeline call is bounded:

```python
return await _get_timeline(
    topic=str(topic),
    since=datetime(1970, 1, 1, tzinfo=UTC),
    limit=100,
)
```

That `since=epoch` makes the resource return everything cached for the topic — clients can re-call `get_timeline` with tighter bounds for narrower views.

## When to prefer resources over tools

Resources are best for:

- Client UIs that browse cached state without modifying it.
- Linking from research notes (the resource URI is stable across sessions).
- Avoiding accidental refresh costs — a resource read on a stale source returns the stale data without re-fetching.

Tools are better when you want fresh data, structured arguments, or write operations.

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/server.py` | All resource handlers |
| `src/anthropic_news_mcp/cache.py` | Storage accessors backing the resources |
