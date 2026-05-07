"""Server integration tests using FastMCP.call_tool()."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.models import Category, NewsItem, Source


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    cache_mod.set_db_path(tmp_path / "server_test.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _seed(source_key: str = "anthropic-newsroom", n: int = 3) -> list[NewsItem]:
    items = [
        NewsItem(
            id=f"srv-{source_key}-{i}",
            title=f"Anthropic update {i}",
            summary=f"Summary {i}",
            url=f"https://anthropic.com/news/{source_key}-{i}",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key=source_key,
            category=[Category.MODELS],
            published_at=datetime(2026, 5, i + 1, tzinfo=timezone.utc),
            importance=2,
        )
        for i in range(n)
    ]
    cache_mod.save_snapshot(source_key, items, ttl_seconds=3600)
    return items


async def _call(tool: str, args: dict) -> dict:  # type: ignore[type-arg]
    from anthropic_news_mcp.server import mcp

    result = await mcp.call_tool(tool, args)
    # MCP 1.27 call_tool returns (list[content], raw_result) tuple
    if isinstance(result, tuple):
        content_list, _ = result
        text = content_list[0].text
    elif isinstance(result, list):
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
    elif hasattr(result, "content"):
        text = result.content[0].text
    else:
        text = str(result)
    return json.loads(text)


@pytest.mark.asyncio
async def test_ping() -> None:
    data = await _call("ping", {})
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_list_sources_returns_all() -> None:
    data = await _call("list_sources", {})
    assert "sources" in data
    keys = [s["key"] for s in data["sources"]]
    assert "anthropic-newsroom" in keys
    assert "hn-anthropic" in keys
    assert "reddit-claude" in keys
    assert len(keys) == 7  # All configured sources


@pytest.mark.asyncio
async def test_get_recent_updates_cached_items() -> None:
    _seed("anthropic-newsroom", n=3)
    data = await _call(
        "get_recent_updates", {"sources": ["anthropic-newsroom"], "limit": 10}
    )
    assert len(data["items"]) == 3
    assert "sources" in data


@pytest.mark.asyncio
async def test_get_recent_updates_category_filter() -> None:
    items = [
        NewsItem(
            id="cat-models",
            title="Model update",
            summary="",
            url="https://anthropic.com/news/model",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            importance=2,
        ),
        NewsItem(
            id="cat-community",
            title="Community post",
            summary="",
            url="https://anthropic.com/news/community",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.COMMUNITY],
            published_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
            importance=1,
        ),
    ]
    cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-newsroom"], "categories": ["models"]},
    )
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "cat-models"


@pytest.mark.asyncio
async def test_get_recent_updates_since_filter() -> None:
    _seed("anthropic-newsroom", n=3)  # May 1, 2, 3 2026
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-newsroom"], "since": "2026-05-02T00:00:00Z"},
    )
    assert len(data["items"]) == 2  # May 2 and 3


@pytest.mark.asyncio
async def test_get_recent_updates_limit() -> None:
    _seed("anthropic-newsroom", n=5)
    data = await _call(
        "get_recent_updates", {"sources": ["anthropic-newsroom"], "limit": 2}
    )
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_search_updates_finds_items() -> None:
    _seed("anthropic-newsroom", n=3)
    data = await _call("search_updates", {"query": "anthropic"})
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["query"] == "anthropic"


@pytest.mark.asyncio
async def test_search_updates_no_match() -> None:
    _seed("anthropic-newsroom", n=2)
    data = await _call("search_updates", {"query": "xyzzy_nomatch_9999"})
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_source_health_all_sources() -> None:
    from anthropic_news_mcp.config import SOURCE_REGISTRY

    data = await _call("get_source_health", {})
    returned_keys = {s["key"] for s in data["sources"]}
    configured_keys = {s.key for s in SOURCE_REGISTRY}
    assert configured_keys == returned_keys
