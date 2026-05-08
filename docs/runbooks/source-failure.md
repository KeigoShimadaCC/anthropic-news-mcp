# Runbook: Source Failure

## When to Use

A news source is returning errors, empty results, or stale data.

## Diagnosis

### Step 1: Check source health

```bash
# Via MCP tool (if server is running):
# Call get_source_health and look for status != "live" or "cache"

# Via audit CLI (live HTTP):
.venv/bin/anthropic-news-audit --sources <source_key>
# or audit all:
.venv/bin/anthropic-news-audit
```

Statuses:
- `live` — fetched successfully this run
- `cache` — served from cache (within TTL)
- `stale` — cache expired, last fetch failed; stale items returned
- `down` — cache empty, last fetch failed; no items
- `not_fetched` — never fetched this session

### Step 2: Identify the error

```bash
# Run audit with verbose output (JSON)
.venv/bin/anthropic-news-audit --sources <source_key> --json /tmp/audit.json
cat /tmp/audit.json | python3 -m json.tool
```

Look at `sources[].error` for the sanitized error message.

Common errors:
- `Connection refused` / `timeout` — network issue or upstream down
- `403 Forbidden` / `429 Too Many Requests` — rate limit or IP block
- `Parse error` — upstream HTML/JSON structure changed
- `0 items` with no error — source returned empty (check `warnings` field)

### Step 3: Test live fetch manually

```bash
# Run the fetcher directly (bypasses cache)
python3 -c "
import asyncio
from anthropic_news_mcp.config import SOURCE_REGISTRY
cfg = next(c for c in SOURCE_REGISTRY if c.key == '<source_key>')
items = asyncio.run(cfg.fetcher_cls().fetch())
print(f'{len(items)} items fetched')
for item in items[:3]:
    print(item.title, item.url)
"
```

## Recovery Actions

### Transient network failure

The server auto-retries with exponential backoff (tenacity). If the source is temporarily
down, the stale cache serves last-known items. No action required beyond monitoring.

### Upstream HTML structure changed (parser broken)

1. Fetch the live page:
   ```bash
   curl -s "https://<source_url>" > tests/fixtures/<source_key>-new.html
   ```
2. Update the fetcher parser in `src/anthropic_news_mcp/fetchers/<name>.py`
3. Update the test fixture and ensure the test passes:
   ```bash
   .venv/bin/pytest tests/test_fetchers/test_<name>.py -v
   ```
4. Bump the fixture in `tests/fixtures/<source_key>.html`

### Rate limit / IP block

- Check if a `User-Agent` header is needed (add to the fetcher's `httpx.AsyncClient`)
- Increase the source `ttl_seconds` in `config.py` to reduce fetch frequency
- If blocked, disable the source temporarily: set `enabled=False` in `config.py`

### Source retired (URL dead)

1. Set `enabled=False` for the source in `config.py`
2. Open a GitHub Issue to track removal or replacement

## Escalation

If a canonical source (`anthropic-newsroom`, `anthropic-docs-api`, etc.) is down for
more than 24 hours, open a GitHub Issue with the audit JSON output attached.
