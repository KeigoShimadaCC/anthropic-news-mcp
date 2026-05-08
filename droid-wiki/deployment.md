# Deployment

The server has two deployment modes — both share the same `mcp` instance from `src/anthropic_news_mcp/server.py`.

## Mode 1: Stdio (local)

The default. The MCP client launches the server process; the server reads JSON-RPC on stdin and writes responses on stdout. This is the right mode for desktop clients.

### Install and configure

See [Getting started](./overview/getting-started.md). The minimal Claude Desktop config:

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "uvx",
      "args": ["anthropic-news-mcp"],
      "env": {"GITHUB_TOKEN": "ghp_optional_token"}
    }
  }
}
```

Restart the client. The 15 tools register automatically.

### State

Stdio mode reads and writes a single SQLite cache file at `~/.cache/anthropic-news-mcp/cache.db`. Override with `ANTHROPIC_NEWS_MCP_CACHE_DB`. The cache survives restarts; clearing it forces a full refetch on next call.

### Logs

Standard Python `logging` to stderr. Wrap with a shell redirect or your client's log pipe to capture.

## Mode 2: Streamable HTTP (remote)

The same server can run as an ASGI app over MCP's Streamable HTTP transport, with OIDC bearer token auth and host/origin allowlists.

### Install

```bash
pip install "anthropic-news-mcp[remote]"
```

The `[remote]` extra adds `PyJWT[crypto]`, `starlette`, `uvicorn`.

### Required environment

Startup fails unless all four are set:

| Variable | Example |
|----------|---------|
| `ANTHROPIC_NEWS_MCP_AUTH_ISSUER` | `https://issuer.example` |
| `ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE` | `anthropic-news` |
| `ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS` | `mcp.example.com` |
| `ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS` | `https://client.example` |

Optional:

- `ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES` (default `anthropic-news:read`)
- `ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL` (default `https://<first allowed host>`)
- `ANTHROPIC_NEWS_MCP_RATE_LIMIT_PER_MINUTE` (default `120`)
- `ANTHROPIC_NEWS_MCP_RATE_LIMIT_BURST` (default `30`)

### Run

```bash
uvicorn anthropic_news_mcp.asgi:app --host 0.0.0.0 --port 8000
```

The MCP endpoint is `/mcp`.

### Trust model

The remote server is a resource server only — it validates JWT bearer tokens against the configured OIDC issuer's JWKS endpoint and never issues tokens itself. Token issuance, refresh, and consent live with the OIDC provider.

The two middlewares enforce:

- Host allowlist on the `Host` header (HTTP 403 otherwise)
- Origin allowlist on the `Origin` header when present (HTTP 403 otherwise)
- Per-client-IP token-bucket rate limit (HTTP 429 otherwise)
- DNS rebinding protection via `mcp.settings.transport_security`

The token bucket is in-memory and process-local — for multi-process deployments, put rate limiting at the edge (an HTTP gateway, CDN, or shared Redis bucket).

### Operational logging

Every remote request gets an `x-request-id` header (generated if the client didn't send one). The middleware logs structured `remote_request` records at INFO with method, path, status code, duration in ms, and client IP. Rejections log structured warnings at WARNING level (`remote_request_denied` with reason).

### Behind a proxy

Common pattern: terminate TLS at an ingress (e.g. an HTTPS load balancer or `nginx`), forward `Host` and `X-Forwarded-For` to the ASGI app, and enforce TLS at the proxy layer. The server's host allowlist still applies — set `ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS` to whatever hostname clients see.

### State

The remote mode reads and writes the same SQLite cache as stdio. For container deployments, mount a persistent volume at the path you set in `ANTHROPIC_NEWS_MCP_CACHE_DB`.

## Mode 3: Live audit (CLI)

Not really a deployment, but worth noting: `anthropic-news-audit` is a separate CLI that imports the source registry and runs every fetcher live. See [Audit CLI](./apps/audit-cli.md).

## Environment summary

| Var | Stdio | Remote | Audit | Eval |
|-----|-------|--------|-------|------|
| `GITHUB_TOKEN` | optional | optional | optional | optional |
| `ANTHROPIC_NEWS_MCP_CACHE_DB` | optional | optional | unused | optional |
| `XDG_CACHE_HOME` | optional | optional | unused | optional |
| `ANTHROPIC_NEWS_MCP_AUTH_*` / `ALLOWED_*` | unused | required | unused | unused |
| `ANTHROPIC_NEWS_MCP_RATE_LIMIT_*` | unused | optional | unused | unused |
| `ANTHROPIC_API_KEY` | unused | unused | unused | required |

## Multi-instance considerations

The README calls out "Multi-instance shared storage is future work." Concretely:

- The SQLite cache supports concurrent readers in one process (WAL mode) but is not designed for cross-host sharing.
- The token-bucket rate limiter is process-local.
- Source health rows reflect the most recent fetch in this instance, not a global view.

For multi-instance deployments today: run a single primary that does fetching and serves a read-only replica path to others, or accept duplicate fetches with eventual consistency. A future refactor could swap SQLite for a network store and move rate limiting to the edge.

## Health and observability

There's no `/healthz` endpoint in the remote ASGI app. Use the `ping` tool over MCP, or rely on uvicorn's built-in graceful shutdown signals. For deeper introspection, the `get_source_health` tool returns per-source state.

## Releases

The package version lives in `src/anthropic_news_mcp/__init__.py` (`__version__ = "0.1.0"`). At the time of writing, the package isn't published to PyPI; the README's `uv tool install anthropic-news-mcp` and `pipx install anthropic-news-mcp` instructions are aspirational. Until publish, install from source.
