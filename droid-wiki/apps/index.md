# Apps

The repo ships three runnable surfaces. All three share the same source code and import the same `mcp` server instance — they differ only in transport and lifecycle.

| App | Entry point | Transport | When to use |
|-----|-------------|-----------|-------------|
| [Stdio MCP server](./mcp-server.md) | `anthropic-news-mcp` (script) or `python -m anthropic_news_mcp` | MCP over stdin/stdout | Local clients (Claude Desktop, Cursor, ChatGPT Desktop) |
| [Remote ASGI deployment](./remote-asgi.md) | `anthropic_news_mcp.asgi:app` | MCP Streamable HTTP at `/mcp` | Multi-tenant or remote-hosted MCP service with OIDC auth |
| [Source-audit CLI](./audit-cli.md) | `anthropic-news-audit` | CLI (no MCP) | Live source health checks, opt-in only |

Both server modes register the same 15 tools, 7 resources, and 6 prompts via the FastMCP instance defined in `src/anthropic_news_mcp/server.py`. The audit CLI is a separate program that imports the source registry directly.

## Console scripts

`pyproject.toml` declares two console scripts:

```toml
[project.scripts]
anthropic-news-mcp = "anthropic_news_mcp.server:main"
anthropic-news-audit = "anthropic_news_mcp.audit:main"
```

Installing the package puts both on `PATH`.

## Process model

```mermaid
graph TD
    subgraph Stdio
        Client1[MCP client] -->|stdin/stdout| Server1[anthropic-news-mcp]
        Server1 -->|reads/writes| Cache1[(cache.db)]
    end
    subgraph ASGI
        Client2[MCP client] -->|HTTPS /mcp| Uvicorn[uvicorn / asgi]
        Uvicorn -->|JWT auth| MCP2[mcp instance]
        MCP2 -->|reads/writes| Cache2[(cache.db)]
    end
    subgraph Audit
        User[Human] -->|CLI| Audit[anthropic-news-audit]
        Audit -->|live HTTP| Web[Source endpoints]
    end
```

The stdio and ASGI modes share the same Pydantic models, retrieval logic, fetchers, and SQLite cache. The audit CLI also shares the fetchers and the source registry but bypasses the cache entirely — it always performs live HTTP.
