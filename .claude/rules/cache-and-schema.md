---
paths:
  - "src/anthropic_news_mcp/cache.py"
  - "src/anthropic_news_mcp/retrieval.py"
---

# Cache & schema rules

- `cache.py` is the **only** writer of the SQLite DB. Retrieval, research, and tests go through it; do not open ad-hoc SQLite connections elsewhere.
- Every public cache function calls `init_db()` first (idempotent, guarded by `_db_initialized`). Reuse the `_conn()` context manager — do not share handles.
- **Any** schema change (new table, new column, new index, FTS change) requires bumping `CACHE_SCHEMA_VERSION`. Mismatch triggers drop-and-recreate on next start.
- `set_db_path(path)` resets `_db_initialized`. Tests rely on this via an autouse fixture pointing at `tmp_path`.
- Canonical env var: `ANTHROPIC_NEWS_MCP_CACHE_DB` (absolute path required).
- URL canonicalization for dedup lives in `retrieval._canonicalize_url`: drop fragment, drop `utm_*` params, decode + sort remaining params. New tracking-param family → extend `_UTM_RE`, not a new helper.
- Trust-ranked dedup tuple is `(_source_rank, _tier_rank, has_published_at, importance, summary_len_clamped, -registry_order)`. Changes here affect every duplicate cluster — ask before editing.
- Error strings stored in `source_snapshots` go through `_sanitize_error` (truncate + strip secrets via `_SECRET_VALUE_RE`). Never log raw exception messages from external HTTP responses.
- Cache reset procedure lives in [docs/runbooks/cache-reset.md](../../docs/runbooks/cache-reset.md).
