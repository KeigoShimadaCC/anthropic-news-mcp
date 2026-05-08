# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (use the project venv)
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Run all tests
.venv/bin/pytest tests/ -v

# Run a single test file
.venv/bin/pytest tests/test_cache.py -v

# Run a single test by name
.venv/bin/pytest tests/test_server.py::test_ping -v

# Lint
.venv/bin/ruff check .

# Format
.venv/bin/ruff format .

# Type check (excludes evals/)
.venv/bin/mypy --strict src/

# Run the server locally (stdio mode)
.venv/bin/anthropic-news-mcp
# or
.venv/bin/python -m anthropic_news_mcp

# Run eval suite (requires ANTHROPIC_API_KEY; costs ~$0.15)
.venv/bin/python evals/run_eval.py
# Run specific prompts only
.venv/bin/python evals/run_eval.py --ids q01,q08,q18
```

## Architecture

The server is built on **FastMCP** (`mcp>=1.27`) using stdio transport. Call flow:

```
MCP client → server.py (tool handlers)
                 → retrieval.py (aggregation, dedup, cache logic)
                     → cache.py (SQLite, ~/.cache/anthropic-news-mcp/cache.db)
                     → fetchers/*.py (one per source, async, stateless)
```

### Key modules

- **`server.py`** — Four MCP tools: `ping`, `list_sources`, `get_recent_updates`, `search_updates`, `get_source_health`. Tool functions are named with `_get_recent_updates` / `_search_updates` (underscore-prefixed imports) to avoid shadowing the retrieval functions they call.

- **`retrieval.py`** — `get_recent_updates()` checks TTLs: fresh sources are served from cache, stale/missing sources are fetched concurrently via `asyncio.gather(..., return_exceptions=True)`. Items are deduplicated by canonical URL (fragments + `utm_*` params stripped, remaining params sorted).

- **`cache.py`** — SQLite with WAL mode. Two tables: `source_snapshots` (one row per source, stores the full serialized `items_json`) and `items` (per-item rows for search). `set_db_path()` redirects to a temp path in tests. `CACHE_SCHEMA_VERSION` triggers a full drop-and-recreate on mismatch.

- **`config.py`** — `SOURCE_REGISTRY: list[SourceConfig]` is the single place to add/remove/configure sources. `_build_registry()` is called once at import time and does the fetcher class imports internally to avoid circular imports.

- **`fetchers/base.py`** — `Fetcher` ABC. Implementations must: set `source_key` as a class variable, raise on transport errors (don't swallow), return `[]` on empty, never cache.

- **`models.py`** — `NewsItem` (Pydantic v2) is the canonical data type. `importance` is a `Literal[1, 2, 3]` (not free-form). All `datetime` fields are UTC-aware. `id` format is `"<source-prefix>-<stable-hash-or-native-id>"`.

### Adding a new source

1. Create `src/anthropic_news_mcp/fetchers/<name>.py` subclassing `Fetcher`.
2. Add a `SourceConfig` entry to `_build_registry()` in `config.py`.
3. Add frozen HTML/JSON to `tests/fixtures/` and a parser unit test in `tests/test_fetchers/`.

### Testing approach

All 107 tests are **offline** — no live HTTP. Fetcher tests parse frozen fixtures from `tests/fixtures/`. Cache tests use `set_db_path(tmp_path / "test.db")` via an `autouse` fixture. Server integration tests call `await mcp.call_tool(name, args)` directly (FastMCP 1.27 in-process API); the return value is a `(list[content], raw_dict)` tuple — extract `result[0][0].text` to get the JSON string.

### Eval harness

`evals/run_eval.py` calls tools in-process (same `mcp.call_tool` pattern), sends results to `claude-haiku-4-5` as judge, scores 0–2 per dimension (tool selection / faithfulness / helpfulness). Pass threshold: mean ≥ 5.0/6.0. Results go to `evals/results/` (gitignored). The eval workflow in `.github/workflows/eval.yml` is manual-trigger only.
