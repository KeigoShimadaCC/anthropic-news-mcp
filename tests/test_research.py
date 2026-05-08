from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.content import build_excerpts, extract_text
from anthropic_news_mcp.models import (
    Category,
    ContentDetail,
    EvidenceTier,
    NewsItem,
    Source,
    SourceType,
)
from anthropic_news_mcp.research import compare_updates, evaluate_claims, search_web_sources


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    cache_mod.set_db_path(tmp_path / "research_test.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _item() -> NewsItem:
    return NewsItem(
        id="research-1",
        title="Claude research update",
        summary="Summary",
        url="https://anthropic.com/news/research-1",  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key="anthropic-newsroom",
        category=[Category.RESEARCH],
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        importance=2,
    )


def test_extract_text_strips_html_boilerplate() -> None:
    text = extract_text(
        "<html><body><nav>menu</nav><main><h1>Title</h1><p>Important evidence.</p></main></body></html>",
        "text/html",
    )
    assert "Important evidence" in text
    assert "menu" not in text


def test_build_excerpts_are_stable() -> None:
    item = _item()
    detail = ContentDetail(
        item_id=item.id,
        url=item.url,
        normalized_text="Claude research includes important evidence about agents and tools.",
        retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
        content_hash="hash",
        content_type="text/html",
    )
    first = build_excerpts(
        item,
        detail,
        source_type=SourceType.OFFICIAL,
        evidence_tier=EvidenceTier.HIGH,
        query="agents",
    )
    second = build_excerpts(
        item,
        detail,
        source_type=SourceType.OFFICIAL,
        evidence_tier=EvidenceTier.HIGH,
        query="agents",
    )
    assert first[0].evidence_id == second[0].evidence_id


def test_compare_updates_and_evaluate_claims() -> None:
    item = _item()
    cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
    detail = ContentDetail(
        item_id=item.id,
        url=item.url,
        normalized_text="Claude research includes important evidence about agents and tools.",
        retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
        content_hash="hash",
        content_type="text/html",
    )
    cache_mod.save_content_detail(detail)
    excerpts = build_excerpts(
        item,
        detail,
        source_type=SourceType.OFFICIAL,
        evidence_tier=EvidenceTier.HIGH,
        query="agents",
    )
    cache_mod.save_evidence_excerpts(excerpts)

    comparison = compare_updates(since=datetime(2026, 1, 1, tzinfo=UTC))
    assert comparison["new_items"]

    results = evaluate_claims(
        claims=["Claude research includes evidence about agents"],
        evidence_ids=[excerpts[0].evidence_id],
    )
    assert results[0].support.value == "strong_support"


def test_compare_updates_detects_disappeared_items() -> None:
    first = _item()
    second = NewsItem(
        id="research-2",
        title="Replacement",
        summary="Summary",
        url="https://anthropic.com/news/research-2",  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key="anthropic-newsroom",
        category=[Category.RESEARCH],
        published_at=datetime(2026, 5, 2, tzinfo=UTC),
        importance=2,
    )
    cache_mod.save_snapshot("anthropic-newsroom", [first], ttl_seconds=3600)
    cache_mod.save_snapshot("anthropic-newsroom", [second], ttl_seconds=3600)
    comparison = compare_updates(since=datetime(2026, 1, 1, tzinfo=UTC))
    assert [item["id"] for item in comparison["disappeared_items"]] == ["research-1"]


@pytest.mark.asyncio
async def test_search_web_sources_matches_cached_detail_text() -> None:
    item = _item()
    cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
    cache_mod.save_content_detail(
        ContentDetail(
            item_id=item.id,
            url=item.url,
            normalized_text="Hidden constitutional evaluation evidence.",
            retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
            content_hash="detail-search",
            content_type="text/html",
        )
    )

    result = await search_web_sources(
        query="constitutional",
        sources=["anthropic-newsroom"],
        limit=5,
    )

    assert result["items"][0]["id"] == item.id
    assert result["evidence"]


@pytest.mark.asyncio
async def test_search_web_sources_refresh_skips_cached_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _item()
    cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
    cache_mod.save_content_detail(
        ContentDetail(
            item_id=item.id,
            url=item.url,
            normalized_text="Cached evidence about agents.",
            retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
            content_hash="cached-detail",
            content_type="text/html",
        )
    )

    async def fail_fetch(news_item: NewsItem) -> ContentDetail:
        raise AssertionError(f"unexpected refresh for {news_item.id}")

    monkeypatch.setattr("anthropic_news_mcp.research.fetch_content_detail", fail_fetch)

    result = await search_web_sources(
        query="agents",
        sources=["anthropic-newsroom"],
        refresh=True,
        limit=5,
    )

    assert result["items"][0]["id"] == item.id


@pytest.mark.asyncio
async def test_search_web_sources_refresh_caps_detail_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [
        NewsItem(
            id=f"refresh-{i}",
            title=f"Refresh target {i}",
            summary="agent detail",
            url=f"https://anthropic.com/news/refresh-{i}",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.RESEARCH],
            published_at=datetime(2026, 5, i + 1, tzinfo=UTC),
            importance=2,
        )
        for i in range(25)
    ]
    cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
    fetched: list[str] = []

    async def fetch(news_item: NewsItem) -> ContentDetail:
        fetched.append(news_item.id)
        return ContentDetail(
            item_id=news_item.id,
            url=news_item.url,
            normalized_text=f"Fetched detail for {news_item.id}",
            retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
            content_hash=f"hash-{news_item.id}",
            content_type="text/html",
        )

    monkeypatch.setattr("anthropic_news_mcp.research.fetch_content_detail", fetch)

    await search_web_sources(
        query="Refresh",
        sources=["anthropic-newsroom"],
        refresh=True,
        limit=25,
    )

    assert len(fetched) == 20
