---
paths:
  - "src/anthropic_news_mcp/server.py"
  - "src/anthropic_news_mcp/research.py"
---

# MCP tool handler rules

- Validate input with the existing `_parse_*` helpers (`_parse_sources`, `_parse_categories`, `_parse_source_types`, `_parse_importance`, `_parse_since`, `_parse_limit`, `_validate_time_range`). They return `(value, error_dict|None)`.
- Return `_error(message, **details)` envelopes for invalid input — shape: `{"error": {"code", "message", "details"}}`. Never raise to the client.
- Re-import retrieval/research functions with an underscore prefix so the MCP tool function names don't shadow the implementations (e.g. `from .retrieval import get_recent_updates as _get_recent_updates`).
- Annotate parameters with `Annotated[..., Field(...)]` for FastMCP schema generation.
- Choose the right `ToolAnnotations`: `READ_ONLY`, `OPEN_WORLD_READ`, or `LOCAL_WRITE`.
- Preserve the untrusted-data warning. Server-level warning is in `SERVER_INSTRUCTIONS`; tools that return fetched body text should repeat it in the docstring.
- Research tools are **evidence-first**. They return excerpts, hashes, and support labels — they do not call an LLM or generate prose. Prose generation is the client's job.
- After adding/removing a tool: regenerate `docs/schema.json` (CI does this via pdoc; smoke-test with `python -c "from anthropic_news_mcp.server import mcp; print('ok')"`).
- Wrap tool entry points in `@track_tool(...)` if you want analytics parity with the existing surface — see `analytics.py`.
- Server integration tests call `await mcp.call_tool(name, args)`; the return is a `(list[content], raw_dict)` tuple — read `result[0][0].text` for the JSON string.
