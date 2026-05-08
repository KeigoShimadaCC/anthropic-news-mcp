# API

The MCP surface is split across three primitives: tools (15), resources (7), and prompts (6). All defined in `src/anthropic_news_mcp/server.py`.

| Page | Surface | Count |
|------|---------|-------|
| [Tools](./tools.md) | Callable functions with structured arguments | 15 |
| [Resources](./resources.md) | URI-templated read-only state | 7 |
| [Prompts](./prompts.md) | Pre-baked instruction templates | 6 |

## Tool annotations

Tools carry `ToolAnnotations` hints that tell clients what side effects to expect:

| Annotation | Used by | Meaning |
|------------|---------|---------|
| `READ_ONLY` | `ping`, `list_sources`, `get_source_health`, `compare_updates`, `get_research_session`, `evaluate_claims` | Reads only the local cache; idempotent |
| `OPEN_WORLD_READ` | `get_recent_updates`, `search_updates`, `get_update_detail`, `search_web_sources`, `get_timeline`, `build_digest_context` | May trigger live HTTP refreshes |
| `LOCAL_WRITE` | `create_research_session`, `save_research_note`, `save_research_report` | Writes local research session state |

## Error envelope

Every tool that validates arguments returns errors in a consistent shape:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Unknown source keys: ['anthropic-typo']. Use list_sources to see valid keys.",
    "details": {"unknown": ["anthropic-typo"], "valid": ["anthropic-newsroom", ...]}
  }
}
```

The `_error(message, **details)` helper in `src/anthropic_news_mcp/server.py` produces this envelope. The eval harness's offline cases assert specific fragments of the message; clients can rely on the shape.

## Untrusted external data

Tool docstrings explicitly mark fetched titles, summaries, authors, tags, and URLs as untrusted external data. The server's top-level `SERVER_INSTRUCTIONS` repeats the warning. Clients that parse and present this data should treat it as content to display, not as instructions to follow.

## Versioning

The `__version__` string in `src/anthropic_news_mcp/__init__.py` (currently `0.1.0`) is what `ping` returns. There's no separate API version — additions to the tool surface are minor version bumps; breaking changes to tool shapes are major.
