import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.models import Category, NewsItem, Source, SourceStatus


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    """Point the cache at a fresh temp DB for each test."""
    cache_mod.set_db_path(tmp_path / "test_cache.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _item(id: str, url: str = "https://anthropic.com/news/test") -> NewsItem:
    return NewsItem(
        id=id,
        title=f"Title {id}",
        summary=f"Summary for {id}",
        url=url,  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key="anthropic-newsroom",
        category=[Category.MODELS],
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        importance=2,
    )


class TestInit:
    def test_init_creates_tables(self, tmp_path: Path) -> None:
        cache_mod.init_db()
        import sqlite3

        db = sqlite3.connect(str(cache_mod.get_db_path()))
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        db.close()
        assert "source_snapshots" in tables
        assert "items" in tables

    def test_idempotent_init(self) -> None:
        cache_mod.init_db()
        cache_mod.init_db()  # Should not raise


class TestFreshness:
    def test_not_fresh_when_empty(self) -> None:
        assert not cache_mod.is_fresh("anthropic-newsroom")

    def test_fresh_after_save(self) -> None:
        items = [_item("a1")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        assert cache_mod.is_fresh("anthropic-newsroom")

    def test_stale_after_ttl(self) -> None:
        items = [_item("a2")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=0)
        # TTL=0 means expired immediately (expires_at == now, not > now)
        assert not cache_mod.is_fresh("anthropic-newsroom")

    def test_freshness_negative_ttl_treated_as_expired(self) -> None:
        items = [_item("a3")]
        # Simulate past expiry by saving with ttl=0
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=0)
        assert not cache_mod.is_fresh("anthropic-newsroom")


class TestSaveAndRetrieve:
    def test_round_trip(self) -> None:
        item = _item("b1", url="https://anthropic.com/news/unique")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        result = cache_mod.get_cached_items("anthropic-newsroom")
        assert len(result) == 1
        assert result[0].id == "b1"
        assert result[0].title == "Title b1"

    def test_empty_source_returns_empty_list(self) -> None:
        result = cache_mod.get_cached_items("nonexistent-source")
        assert result == []

    def test_snapshot_replaces_previous(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("c1")], ttl_seconds=3600)
        cache_mod.save_snapshot("anthropic-newsroom", [_item("c2"), _item("c3")], ttl_seconds=3600)
        result = cache_mod.get_cached_items("anthropic-newsroom")
        assert len(result) == 2
        assert {r.id for r in result} == {"c2", "c3"}

    def test_multiple_sources_isolated(self) -> None:
        cache_mod.save_snapshot("src-a", [_item("d1")], ttl_seconds=3600)
        cache_mod.save_snapshot("src-b", [_item("d2")], ttl_seconds=3600)
        assert len(cache_mod.get_cached_items("src-a")) == 1
        assert len(cache_mod.get_cached_items("src-b")) == 1

    def test_get_snapshot_returns_health(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("e1")], ttl_seconds=1800)
        health = cache_mod.get_snapshot("anthropic-newsroom")
        assert health is not None
        assert health.key == "anthropic-newsroom"
        assert health.status == SourceStatus.LIVE
        assert health.item_count == 1
        assert health.error is None

    def test_get_snapshot_none_when_missing(self) -> None:
        assert cache_mod.get_snapshot("missing") is None

    def test_save_with_error_status(self) -> None:
        cache_mod.save_snapshot(
            "anthropic-newsroom",
            [],
            ttl_seconds=0,
            status=SourceStatus.DOWN,
            error="connection refused",
        )
        health = cache_mod.get_snapshot("anthropic-newsroom")
        assert health is not None
        assert health.status == SourceStatus.DOWN
        assert health.error == "connection refused"


class TestSearch:
    def test_search_by_title(self) -> None:
        item = NewsItem(
            id="s1",
            title="Claude 3.5 Sonnet Released",
            summary="Major capability improvements",
            url="https://anthropic.com/news/sonnet",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            importance=3,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        results = cache_mod.search_items("sonnet")
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_search_case_insensitive(self) -> None:
        item = _item("s2")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        assert len(cache_mod.search_items("TITLE")) == 1
        assert len(cache_mod.search_items("title")) == 1

    def test_search_no_match_returns_empty(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("s3")], ttl_seconds=3600)
        results = cache_mod.search_items("xyzzy_nomatch")
        assert results == []

    def test_search_wildcard_percent_not_expanded(self) -> None:
        """'%' must be treated as a literal character, not a LIKE wildcard."""
        item_a = NewsItem(
            id="w1",
            title="Claude 3 update",
            summary="A real item",
            url="https://anthropic.com/news/w1",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            importance=1,
        )
        item_b = NewsItem(
            id="w2",
            title="Unrelated post",
            summary="No match here",
            url="https://anthropic.com/news/w2",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            importance=1,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item_a, item_b], ttl_seconds=3600)
        # Without fix: "%" → LIKE "%%" → matches every row (any sequence)
        # With fix:    "%" → LIKE "%\%%" ESCAPE '\' → literal "%" not in any payload → empty
        results = cache_mod.search_items("%")
        assert results == [], f"'%' should match nothing, got {len(results)} items"

    def test_search_wildcard_underscore_not_expanded(self) -> None:
        """'_' in a query must be treated as a literal character, not an any-char wildcard."""
        # item whose title contains "xspecial" — vulnerable LIKE "_special" would match
        # it (via x ↔ _), but the fixed literal search for "_special" should not.
        item_a = NewsItem(
            id="u1",
            title="xspecial announcement",
            summary="Contains xspecial",
            url="https://anthropic.com/news/u1",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            importance=1,
        )
        item_b = NewsItem(
            id="u2",
            title="Regular news",
            summary="Nothing here",
            url="https://anthropic.com/news/u2",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            importance=1,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item_a, item_b], ttl_seconds=3600)
        # Without fix: "_special" → LIKE "%_special%" → matches "xspecial" → returns item_a
        # With fix:    "_special" → LIKE "%\_special%" ESCAPE '\' → literal "_special"
        #              not present in either payload → returns nothing
        results = cache_mod.search_items("_special")
        assert results == [], f"'_special' wildcard should not match 'xspecial', got {len(results)} items"

    def test_search_respects_limit(self) -> None:
        items = [
            NewsItem(
                id=f"lim{i}",
                title=f"Anthropic update {i}",
                summary="",
                url=f"https://anthropic.com/news/{i}",  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key="anthropic-newsroom",
                category=[],
                published_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                importance=1,
            )
            for i in range(10)
        ]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        results = cache_mod.search_items("anthropic", limit=3)
        assert len(results) == 3


class TestGetAllSnapshots:
    def test_returns_all_sources(self) -> None:
        cache_mod.save_snapshot("src-x", [_item("x1")], ttl_seconds=3600)
        cache_mod.save_snapshot("src-y", [_item("y1")], ttl_seconds=3600)
        healths = cache_mod.get_all_snapshots()
        keys = {h.key for h in healths}
        assert keys == {"src-x", "src-y"}

    def test_empty_when_no_data(self) -> None:
        assert cache_mod.get_all_snapshots() == []
