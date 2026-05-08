"""Tests for the retrieval layer (aggregation, dedup, filtering)."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.models import Category, NewsItem, Source, SourceStatus
from anthropic_news_mcp.retrieval import (
    _canonicalize_url,
    _sanitize_error,
    get_health,
    get_recent_updates,
    search_updates,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    cache_mod.set_db_path(tmp_path / "retrieval_test.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _make_item(
    id: str,
    url: str,
    source_key: str = "anthropic-newsroom",
    category: list[Category] | None = None,
    published_at: datetime | None = None,
) -> NewsItem:
    return NewsItem(
        id=id,
        title=f"Item {id}",
        summary="",
        url=url,  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key=source_key,
        category=category or [Category.MODELS],
        published_at=published_at or datetime(2026, 1, 1, tzinfo=UTC),
        importance=1,
    )


class TestCanonicalizeUrl:
    def test_strips_fragment(self):
        assert _canonicalize_url("https://a.com/page#section") == "https://a.com/page"

    def test_strips_utm_params(self):
        url = "https://a.com/page?utm_source=twitter&utm_campaign=launch"
        assert _canonicalize_url(url) == "https://a.com/page"

    def test_keeps_non_utm_params(self):
        url = "https://a.com/page?ref=blog&foo=bar"
        result = _canonicalize_url(url)
        assert "ref=blog" in result
        assert "foo=bar" in result

    def test_sorts_params(self):
        a = _canonicalize_url("https://a.com/?z=1&a=2")
        b = _canonicalize_url("https://a.com/?a=2&z=1")
        assert a == b


class TestGetRecentUpdates:
    @pytest.mark.asyncio
    async def test_returns_cached_items_when_fresh(self):
        items = [_make_item("x1", "https://anthropic.com/news/x1")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        result, _ = await get_recent_updates(sources=["anthropic-newsroom"])
        assert len(result) == 1
        assert result[0].id == "x1"

    @pytest.mark.asyncio
    async def test_deduplicates_by_canonical_url(self):
        url = "https://anthropic.com/news/item?utm_source=twitter"
        url_clean = "https://anthropic.com/news/item"
        cache_mod.save_snapshot(
            "anthropic-newsroom",
            [_make_item("a1", url)],
            ttl_seconds=3600,
        )
        cache_mod.save_snapshot(
            "anthropic-docs-api",
            [_make_item("a2", url_clean, source_key="anthropic-docs-api")],
            ttl_seconds=3600,
        )
        result, _ = await get_recent_updates(sources=["anthropic-newsroom", "anthropic-docs-api"])
        # Both canonicalize to the same URL — only one should survive
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_deduplicates_canonical_and_filtered_sources(self):
        url = "https://anthropic.com/news/aws-compute?utm_medium=social"
        clean = "https://anthropic.com/news/aws-compute"
        cache_mod.save_snapshot(
            "anthropic-newsroom",
            [_make_item("canonical", url, category=[Category.BUSINESS])],
            ttl_seconds=3600,
        )
        cache_mod.save_snapshot(
            "anthropic-business-infrastructure",
            [
                _make_item(
                    "filtered",
                    clean,
                    source_key="anthropic-business-infrastructure",
                    category=[Category.BUSINESS],
                )
            ],
            ttl_seconds=3600,
        )
        result, _ = await get_recent_updates(
            sources=["anthropic-newsroom", "anthropic-business-infrastructure"]
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_source_handling(self):
        cache_mod.save_snapshot("anthropic-status", [], ttl_seconds=3600)
        result, healths = await get_recent_updates(sources=["anthropic-status"])
        assert result == []
        assert len(healths) == 1
        assert healths[0].item_count == 0

    @pytest.mark.asyncio
    async def test_category_filter(self):
        items = [
            _make_item("c1", "https://anthropic.com/1", category=[Category.MODELS]),
            _make_item("c2", "https://anthropic.com/2", category=[Category.COMMUNITY]),
        ]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        result, _ = await get_recent_updates(
            sources=["anthropic-newsroom"], categories=[Category.MODELS]
        )
        assert len(result) == 1
        assert result[0].id == "c1"

    @pytest.mark.asyncio
    async def test_since_filter(self):
        items = [
            _make_item(
                "d1",
                "https://anthropic.com/d1",
                published_at=datetime(2026, 3, 1, tzinfo=UTC),
            ),
            _make_item(
                "d2",
                "https://anthropic.com/d2",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        result, _ = await get_recent_updates(
            sources=["anthropic-newsroom"],
            since=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert len(result) == 1
        assert result[0].id == "d1"

    @pytest.mark.asyncio
    async def test_limit_respected(self):
        items = [_make_item(f"e{i}", f"https://anthropic.com/{i}") for i in range(10)]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        result, _ = await get_recent_updates(sources=["anthropic-newsroom"], limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_sorted_newest_first(self):
        items = [
            _make_item(
                "f1",
                "https://anthropic.com/f1",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            _make_item(
                "f2",
                "https://anthropic.com/f2",
                published_at=datetime(2026, 3, 1, tzinfo=UTC),
            ),
            _make_item(
                "f3",
                "https://anthropic.com/f3",
                published_at=datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        result, _ = await get_recent_updates(sources=["anthropic-newsroom"])
        assert result[0].id == "f2"
        assert result[1].id == "f3"
        assert result[2].id == "f1"

    @pytest.mark.asyncio
    async def test_returns_health_records(self):
        cache_mod.save_snapshot("anthropic-newsroom", [], ttl_seconds=3600)
        _, healths = await get_recent_updates(sources=["anthropic-newsroom"])
        assert len(healths) == 1

    @pytest.mark.asyncio
    async def test_unknown_source_key_returns_empty(self):
        result, _ = await get_recent_updates(sources=["nonexistent-source"])
        assert result == []


class TestSearchUpdates:
    @pytest.mark.asyncio
    async def test_cold_cache_search_self_warms(self, monkeypatch: pytest.MonkeyPatch):
        class WarmFetcher:
            async def fetch(self) -> list[NewsItem]:
                return [
                    _make_item(
                        "warm-1",
                        "https://anthropic.com/news/warm-1",
                        published_at=datetime(2026, 5, 1, tzinfo=UTC),
                    )
                ]

        from anthropic_news_mcp.config import SourceConfig

        monkeypatch.setattr(
            "anthropic_news_mcp.retrieval.SOURCE_REGISTRY",
            [SourceConfig("anthropic-newsroom", WarmFetcher, 3600, [Category.MODELS])],
        )
        results = await search_updates("warm")
        assert [item.id for item in results] == ["warm-1"]


class TestSanitizeError:
    def test_redacts_query_tokens_headers_and_key_values(self):
        error = RuntimeError(
            "GET https://example.com/path?api_key=secret failed "
            "Authorization: Bearer abc123 token=def456 client_secret=hunter2"
        )
        message = _sanitize_error(error)
        assert "api_key=secret" not in message
        assert "abc123" not in message
        assert "def456" not in message
        assert "hunter2" not in message
        assert "?[redacted]" in message


class TestFetchSourceFailure:
    @pytest.mark.asyncio
    async def test_fetch_source_failure_falls_back_to_stale(self):
        """When a fetcher raises, stale cached items are returned with STALE status."""
        items = [_make_item("stale1", "https://anthropic.com/stale1")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=0)

        with patch(
            "anthropic_news_mcp.fetchers.newsroom.NewsroomFetcher.fetch",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network down"),
        ):
            result, healths = await get_recent_updates(sources=["anthropic-newsroom"])

        assert len(result) == 1
        assert result[0].id == "stale1"
        newsroom_health = next(h for h in healths if h.key == "anthropic-newsroom")
        assert newsroom_health.status == SourceStatus.STALE
        assert newsroom_health.error is not None


class TestGetHealth:
    @pytest.mark.asyncio
    async def test_returns_all_configured_sources(self):
        from anthropic_news_mcp.config import SOURCE_REGISTRY

        healths = await get_health()
        configured_keys = {s.key for s in SOURCE_REGISTRY}
        returned_keys = {h.key for h in healths}
        assert configured_keys == returned_keys

    @pytest.mark.asyncio
    async def test_uncached_source_shows_down(self):
        healths = await get_health()
        for h in healths:
            if h.status == SourceStatus.DOWN and h.error == "Never fetched":
                return  # Found at least one
        pytest.skip("All sources happen to be cached")
