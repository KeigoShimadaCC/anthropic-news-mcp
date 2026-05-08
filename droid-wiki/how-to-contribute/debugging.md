# Debugging

A short runbook for the failure shapes that come up most.

## A source returns no items

Symptoms: `get_recent_updates` returns fewer items than expected, or `list_sources` shows a source with `not_fetched` or `down`.

Steps:

1. Run the live audit for that source:
   ```bash
   .venv/bin/anthropic-news-audit --sources <source-key>
   ```
2. Check `error` and `warnings` in the audit row. The error is sanitized (no secrets) but tells you whether the source returned 4xx/5xx, returned empty, or timed out.
3. If it returned data but no items: the source's HTML structure may have changed. Re-capture the fixture, diff against the existing one, and update the parser.
4. If it timed out: bump the source's TTL temporarily and check whether the issue is rate-limiting (especially GitHub without `GITHUB_TOKEN`).
5. If it 403'd: the source may have changed access policy. Reddit returns 403 sometimes; the fetcher tolerates it by skipping that subreddit. Other 403s usually need a User-Agent or auth fix.

## A page parser broke after an Anthropic redesign

Symptoms: One of the listing fetchers (`newsroom`, `research`, `engineering`) returns far fewer items than expected, or items have empty titles.

Steps:

1. Capture the new HTML:
   ```bash
   curl -sSL "https://www.anthropic.com/news" -o /tmp/newsroom-new.html
   ```
2. Diff against the fixture:
   ```bash
   diff <(.venv/bin/python -c "from selectolax.parser import HTMLParser; t=HTMLParser(open('/tmp/newsroom-new.html').read()); print(t.html[:2000])") <(.venv/bin/python -c "from selectolax.parser import HTMLParser; t=HTMLParser(open('tests/fixtures/newsroom.html').read()); print(t.html[:2000])")
   ```
3. Identify the changed selector. Update `parse_anthropic_listing_html` (or the source-specific parser) accordingly.
4. Replace the fixture: `cp /tmp/newsroom-new.html tests/fixtures/newsroom.html`.
5. Re-run the parser tests. Adjust assertions if the page structure genuinely changed (e.g. a date format).

## Cache misbehavior

Symptoms: Stale data persists past the expected TTL, or expected items don't appear in search.

Steps:

1. Verify the cache path. Run a tool that emits a structured log (`get_recent_updates`) and check the resolved DB path. Default is `~/.cache/anthropic-news-mcp/cache.db`.
2. Inspect the cache:
   ```bash
   sqlite3 ~/.cache/anthropic-news-mcp/cache.db
   sqlite> SELECT source_key, status, item_count, expires_at FROM source_snapshots;
   sqlite> SELECT id, source_key, published_at FROM items ORDER BY published_at DESC LIMIT 20;
   sqlite> SELECT * FROM items_fts LIMIT 5;
   ```
3. If the schema looks wrong (missing columns), bump `CACHE_SCHEMA_VERSION` in `src/anthropic_news_mcp/cache.py` to force a rebuild on next run.
4. Quick reset: `rm ~/.cache/anthropic-news-mcp/cache.db` (the WAL files are recreated on next call).

## Smoke-import failure in CI

Symptoms: CI's "Smoke test import" step fails before any tests run.

Steps:

1. The smoke test runs `python -c "from anthropic_news_mcp.server import mcp; print('import ok')"`.
2. Failure usually means a circular import or a broken import inside `_build_registry()`. The `_build_registry()` function imports fetcher classes inside its body specifically to avoid circular imports — make sure new fetcher imports follow the same pattern.
3. Check that any `TYPE_CHECKING` imports in `src/anthropic_news_mcp/config.py` don't accidentally become real imports.

## Mypy strict failure

Symptoms: `mypy --strict` reports `error: Unsupported left operand type for ...` or similar.

Steps:

1. Run mypy locally with the same flags as CI:
   ```bash
   .venv/bin/mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
   ```
2. Common causes:
   - `Any` in a type annotation that needs a concrete shape (use a `TypedDict` or Pydantic model).
   - Missing return type annotation on an async function.
   - `# type: ignore[arg-type]` on a `HttpUrl=str` assignment (this is a known pattern when constructing `NewsItem` from raw data; use `# type: ignore[arg-type]` consistently).
   - Untyped `**kwargs` in `get_client()` — the project uses `**kwargs: object` and casts internally.

## Remote ASGI startup failure

Symptoms: `RuntimeError: Refusing insecure remote MCP startup; missing required environment: ANTHROPIC_NEWS_MCP_AUTH_ISSUER, ...`

Steps:

1. Set all four required env vars: `ANTHROPIC_NEWS_MCP_AUTH_ISSUER`, `ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE`, `ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS`, `ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS`.
2. If JWKS lookup fails on the first request: check the issuer URL is reachable from the server, and that `${issuer}/.well-known/jwks.json` returns a valid JWKS document.
3. Use `tests/test_remote.py` as a reference — it exercises the full auth/middleware chain in-process.

## Reddit / HN rate limiting

Symptoms: `reddit-claude` or `hn-anthropic` returns empty repeatedly.

Steps:

1. Reddit returns 403 when the public JSON endpoints throttle. The fetcher tolerates 403 and 429 by skipping the subreddit.
2. The User-Agent override in `RedditFetcher` (`anthropic-news-mcp/1.0`) is intentional — Reddit blocks default UAs. Don't change it without testing.
3. HN's Algolia API rarely rate-limits but can return empty hits when the `query` matches nothing recent. The 10-point minimum filters quiet days out.

## Logging

Standard Python `logging`. Three notable channels:

- `anthropic_news_mcp.server` — structured `invalid_request` logs at INFO with `error_code`, `error_message`, `error_details`.
- `anthropic_news_mcp.retrieval` — `source_fetch_succeeded` (INFO) and `source_fetch_failed` (WARNING) with sanitized error messages.
- `anthropic_news_mcp.remote` — `remote_request` (INFO) and `remote_request_denied` (WARNING) with request IDs.

In stdio mode, logs go to stderr. Configure the root logger from your client wrapper if you want them to a file.

## When in doubt: read the test

The test suite is the most reliable executable spec. If you're unsure how a function is supposed to behave, find the test that exercises it. Most public functions have direct coverage; integration tests live in `test_server.py`.
