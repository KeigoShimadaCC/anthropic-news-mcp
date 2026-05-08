# Copilot instructions for `anthropic-news-mcp`

## Build, test, and lint commands

Use the project virtualenv so commands run with pinned dev dependencies:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Primary local checks:

```bash
# optional local hooks
.venv/bin/pre-commit install
.venv/bin/pre-commit install --hook-type pre-push

# full test suite (offline)
.venv/bin/pytest tests/ -v

# single test file
.venv/bin/pytest tests/test_cache.py -v

# single test
.venv/bin/pytest tests/test_server.py::test_ping -v

# lint / format / type-check
.venv/bin/ruff check .
.venv/bin/ruff format .
.venv/bin/mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
```

Eval and runtime commands used in this repo:

```bash
# deterministic offline eval
.venv/bin/python evals/run_offline_eval.py

# run MCP server locally (stdio)
.venv/bin/anthropic-news-mcp
# or
.venv/bin/python -m anthropic_news_mcp
```

## High-level architecture

The server is a FastMCP app centered on `src/anthropic_news_mcp/server.py`, which defines MCP tools/resources/prompts and performs input validation (source keys, category enums, time ranges, limits) before delegating business logic.

`retrieval.py` is the aggregation layer: it reads `SOURCE_REGISTRY` from `config.py`, serves fresh sources from cache, fetches stale sources concurrently, sanitizes source errors, and deduplicates merged items by canonical URL before ranking/selecting representatives.

`cache.py` is the persistence layer (SQLite + WAL). It stores source snapshots, searchable item rows/FTS index, content details, evidence excerpts, item history, and research sessions/notes/reports. Retrieval and research flows should go through this layer rather than creating ad-hoc storage.

`research.py` builds higher-level research workflows (`get_update_detail`, `search_web_sources`, `get_timeline`, `compare_updates`, digest context, session/note/report storage, deterministic claim evaluation) on top of cached `NewsItem` and evidence excerpts; tools are evidence-first and do not generate prose with an internal LLM.

`content.py` + `http.py` handle page retrieval and normalization: allowed-host guarded HTTP client, content-type-aware extraction, truncation/warning behavior, and stable excerpt generation with deterministic evidence IDs.

`remote.py`/`asgi.py` provide optional Streamable HTTP deployment with OIDC JWT verification, host/origin enforcement, and request logging + token-bucket rate limiting.

## Key conventions in this codebase

- `config.py` is the single source of truth for supported sources (`SOURCE_REGISTRY`) including TTL, default categories, source type, and evidence tier.
- Fetchers must follow the `Fetcher` contract in `fetchers/base.py`: async + stateless, raise on transport failures, return `[]` for empty results, set `source_key`, and never do internal caching.
- Tool handlers in `server.py` use structured error payloads (`{"error": {"code", "message", "details"}}`) for invalid input instead of throwing user-facing exceptions.
- In `server.py`, retrieval/research imports are underscore-aliased (for example `_get_recent_updates`) to avoid name shadowing with MCP tool functions.
- `NewsItem` in `models.py` is canonical across layers; datetimes are UTC-aware, `importance` is `Literal[1,2,3]`, and derived fields (`sort_at`, `date_confidence`, `is_official`) are set by model validation.
- Dedup and representative selection are URL-canonical + trust-weighted (source type/evidence tier/metadata quality), not first-write-wins.
- External fetched data is treated as untrusted content throughout tools/prompts/resources; preserve this boundary when adding features.
- Tests are intentionally offline: fetcher tests use frozen fixtures, and cache/server tests isolate SQLite with `cache.set_db_path(tmp_path / "...")`.
- FastMCP integration tests call `await mcp.call_tool(...)`; on FastMCP 1.27, handle tuple return shape `(list[content], raw_result)` and read `content[0].text`.
