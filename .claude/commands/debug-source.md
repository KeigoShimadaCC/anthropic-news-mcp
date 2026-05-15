# /debug-source

Diagnose and repair a failing news source.

## Input expected
- Source key (e.g. `anthropic-status`).

## Steps
1. Read [docs/runbooks/source-failure.md](../../docs/runbooks/source-failure.md).
2. Confirm with the user before running live HTTP. Then:
   `.venv/bin/anthropic-news-audit --sources <key> --json /tmp/audit-<key>.json`.
3. Inspect `sources[].error` and `sources[].status` from the JSON.
4. **Parser regression** → capture the live page into a new fixture (`curl -s "<url>" > tests/fixtures/<key>.html`), update the parser in `src/anthropic_news_mcp/fetchers/<name>.py`, re-run `pytest tests/test_fetchers/test_<name>.py -v`.
5. **Rate limit / IP block** → increase `ttl_seconds` in `config.py` or set `enabled=False`.
6. **Host blocked** → confirm the host is in `_ALLOWED_FETCH_HOSTS` in `http.py`.
7. **Transient** → cache serves last-known items; no action beyond monitoring.

## Stop condition
Source returns `live` or `cache` status; parser test passes.

## Output
- Root cause.
- Fix applied (or "not fixed — escalate via GitHub Issue with audit JSON").
- Verification: parser test result + offline eval result.
