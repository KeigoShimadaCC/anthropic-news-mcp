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
from anthropic_news_mcp.research import compare_updates, evaluate_claims


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
