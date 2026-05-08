from datetime import datetime

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import SOURCE_REGISTRY
from .models import Category
from .retrieval import get_health
from .retrieval import get_recent_updates as _get_recent_updates
from .retrieval import search_updates as _search_updates

mcp = FastMCP("anthropic-news")


@mcp.tool()
async def ping() -> dict[str, str]:
    """Health check. Returns ok status and server version."""
    return {"status": "ok", "server": "anthropic-news-mcp", "version": __version__}


@mcp.tool()
async def list_sources() -> dict[str, object]:
    """List all configured news sources with their keys, descriptions, and status.

    Use this to discover available source keys before calling get_recent_updates
    with a sources filter. Returns enabled/disabled status and cache TTL for each.
    """
    return {
        "sources": [
            {
                "key": s.key,
                "description": s.description,
                "enabled": s.enabled,
                "categories": [c.value for c in s.default_categories],
                "ttl_seconds": s.ttl_seconds,
            }
            for s in SOURCE_REGISTRY
        ]
    }


@mcp.tool()
async def get_recent_updates(
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    since: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    """Get recent Anthropic news, model releases, Claude Code changelogs, and community signals.

    Aggregates across all configured sources (newsroom, docs, GitHub, HN, Reddit).
    Results are deduplicated by URL and sorted newest-first.

    Args:
        sources: Optional list of source keys to restrict to, e.g. ["anthropic-newsroom"].
                 Omit to query all enabled sources. Use list_sources to discover keys.
        categories: Optional list of category filters. Valid values:
                    "models", "claude-code", "research", "policy", "business", "community".
        since: Optional ISO 8601 datetime. Only items published after this are returned.
               Example: "2026-04-01T00:00:00Z" or "2026-04-01".
        limit: Maximum items to return. Default 20, max 100.

    Returns:
        {"items": [...NewsItem...], "sources": [...SourceHealth...]}
    """
    if sources:
        if len(sources) > 50:
            return {"error": "Too many source keys — limit is 50 per request."}
        valid_keys = {s.key for s in SOURCE_REGISTRY}
        unknown = [k for k in sources if k not in valid_keys]
        if unknown:
            return {
                "error": f"Unknown source keys: {unknown}. Use list_sources to see valid keys."
            }

    parsed_since: datetime | None = None
    if since:
        try:
            parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            pass

    parsed_categories: list[Category] | None = None
    if categories:
        valid: list[Category] = []
        invalid: list[str] = []
        for c in categories:
            try:
                valid.append(Category(c))
            except ValueError:
                invalid.append(c)
        if invalid:
            valid_values = [cat.value for cat in Category]
            return {
                "error": f"Unknown categories: {invalid}. Valid values: {valid_values}"
            }
        parsed_categories = valid or None

    items, healths = await _get_recent_updates(
        sources=sources,
        categories=parsed_categories,
        since=parsed_since,
        limit=min(limit, 100),
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "sources": [h.model_dump(mode="json") for h in healths],
    }


@mcp.tool()
async def search_updates(query: str, limit: int = 10) -> dict[str, object]:
    """Full-text search across cached items (title, summary, tags). Case-insensitive.

    Searches the local SQLite cache only. If the cache is cold, call
    get_recent_updates first to populate it.

    Args:
        query: Search string. Examples: "claude code v1.2", "RSP", "agents", "Sonnet".
        limit: Maximum items to return. Default 10, max 50.

    Returns:
        {"items": [...NewsItem...], "query": str}
    """
    items = await _search_updates(query=query, limit=min(limit, 50))
    return {"items": [item.model_dump(mode="json") for item in items], "query": query}


@mcp.tool()
async def get_source_health() -> dict[str, object]:
    """Show operational status for each source.

    Returns when each source last fetched successfully, how many items it returned,
    and any error messages. Useful for diagnosing missing data or stale results.

    Returns:
        {"sources": [...SourceHealth...]}
    """
    healths = await get_health()
    return {"sources": [h.model_dump(mode="json") for h in healths]}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
