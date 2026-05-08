# Runbook: Cache Reset

## When to Use

- Cache is corrupt or schema mismatch causes startup errors
- Items are stale and TTL-based refresh is not working
- Switching between environments (dev/prod) and need a clean slate
- After upgrading `CACHE_SCHEMA_VERSION` in `cache.py`

## Symptoms

- Server starts but `get_recent_updates` returns no items
- SQLite errors in server logs (`OperationalError`, `DatabaseError`)
- `get_source_health` shows all sources as `NOT_FETCHED`

## Default Cache Location

```bash
ls ~/.cache/anthropic-news-mcp/cache.db
```

Override with `ANTHROPIC_NEWS_MCP_CACHE` environment variable.

## Reset Procedure

### Option 1: Delete the cache file (full reset)

```bash
# Find the cache path
echo ${ANTHROPIC_NEWS_MCP_CACHE:-~/.cache/anthropic-news-mcp/cache.db}

# Delete it — the server recreates it on next start
rm ~/.cache/anthropic-news-mcp/cache.db
```

The server will rebuild the schema and repopulate all sources on the next `get_recent_updates` call.

### Option 2: Force-expire one source (soft reset)

```bash
# Use sqlite3 to expire a specific source's cache entry
sqlite3 ~/.cache/anthropic-news-mcp/cache.db \
  "UPDATE source_snapshots SET expires_at = '2000-01-01T00:00:00+00:00' WHERE key = 'anthropic-newsroom';"
```

The next `get_recent_updates` call will refetch only that source.

### Option 3: Schema version bump (auto-reset on next start)

In `src/anthropic_news_mcp/cache.py`, increment `CACHE_SCHEMA_VERSION`.
On next server start, the existing DB is dropped and recreated from scratch.

## Verification

After reset:

```bash
# Start the server and call ping
.venv/bin/anthropic-news-mcp &
# (In another terminal, use an MCP client or curl to call ping)

# Or verify via audit CLI
.venv/bin/anthropic-news-audit --sources anthropic-status
```

## Notes

- The SQLite file is user-local; no shared state between users
- Cache rebuild takes 5–30 seconds depending on network speed and source count
- WAL mode is used; do not copy the `.db` file while the server is running
