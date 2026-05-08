# Configuration

All runtime configuration lives in environment variables. There's no config file format — env vars are the surface.

A reference template lives at `.env.example`.

## Cache

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_NEWS_MCP_CACHE_DB` | No | `~/.cache/anthropic-news-mcp/cache.db` | Override the SQLite cache path. Must be an absolute path; relative paths raise on startup. |
| `XDG_CACHE_HOME` | No | `~/.cache` | Parent cache directory if `ANTHROPIC_NEWS_MCP_CACHE_DB` is unset. The server warns if this directory is world-readable. |

## GitHub

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GITHUB_TOKEN` | No | (none) | Optional GitHub personal access token. Without it, the GitHub API limits to 60 req/hr; with it, 5,000 req/hr. No scopes needed for public repos. Honored by `github_releases.py`, `github_events.py`, `github_issues.py`. |

## Eval

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Yes (eval only) | (none) | Required only for `evals/run_eval.py`. The offline eval (`run_offline_eval.py`) does not need a key. |

## Remote ASGI auth

All four are required for the remote ASGI deployment. Startup raises `RuntimeError` if any is missing.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_NEWS_MCP_AUTH_ISSUER` | (required) | OIDC issuer URL. JWKS is fetched from `${issuer}/.well-known/jwks.json`. |
| `ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE` | (required) | Expected `aud` claim on incoming JWTs. |
| `ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS` | (required) | Comma-separated allowlist for the `Host` header. |
| `ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS` | (required) | Comma-separated allowlist for the `Origin` header. |

## Remote ASGI tunables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES` | `anthropic-news:read` | Comma-separated scopes the JWT must include. |
| `ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL` | `https://<first allowed host>` | Resource server URL for the OAuth metadata document. |
| `ANTHROPIC_NEWS_MCP_RATE_LIMIT_PER_MINUTE` | `120` | Token-bucket refill rate per client IP. |
| `ANTHROPIC_NEWS_MCP_RATE_LIMIT_BURST` | `30` | Token-bucket capacity per client IP. |

## Fixed-at-import constants

A few values are fixed in code rather than environment-configurable. Edit the constant if you need a different value.

| Constant | File | Purpose |
|----------|------|---------|
| `_TIMEOUT` | `src/anthropic_news_mcp/http.py` | `httpx.Timeout(15.0, connect=5.0)` |
| `_HEADERS` | `src/anthropic_news_mcp/http.py` | `User-Agent` header for outbound requests |
| `_ALLOWED_FETCH_HOSTS` | `src/anthropic_news_mcp/http.py` | Outbound host allowlist (16 hosts at time of writing) |
| `_MAX_STORED_CHARS` | `src/anthropic_news_mcp/content.py` | `50_000` — content detail truncation |
| `_MAX_RESPONSE_BYTES` | `src/anthropic_news_mcp/content.py` | `5_000_000` — hard byte cap before extraction |
| `_BOILERPLATE_TAGS` | `src/anthropic_news_mcp/content.py` | HTML tags stripped during normalization |
| `CACHE_SCHEMA_VERSION` | `src/anthropic_news_mcp/cache.py` | `3` |
| `_MIN_POINTS` | `src/anthropic_news_mcp/fetchers/hackernews.py` | `10` — HN minimum points filter |
| `_REPOS` | `src/anthropic_news_mcp/fetchers/github_releases.py`, `github_issues.py` | Four GitHub repos covered by these fetchers |
| `_SUBREDDITS` | `src/anthropic_news_mcp/fetchers/reddit.py` | `["ClaudeAI", "anthropic"]` |

## TTL summary

Set in `SOURCE_REGISTRY` in `src/anthropic_news_mcp/config.py`:

| Source | TTL (s) | TTL (min) |
|--------|---------|-----------|
| `anthropic-status` | 300 | 5 |
| `anthropic-newsroom`, `anthropic-github-releases`, `anthropic-github-events`, `anthropic-github-issues-prs`, `hn-anthropic` | 1800 | 30 |
| All `anthropic-research`, `anthropic-engineering`, `anthropic-docs-*`, `anthropic-support-release-notes`, `anthropic-business-infrastructure`, `anthropic-trust-policy`, `reddit-claude` | 3600 | 60 |
| `anthropic-economic-index` | 7200 | 120 |
