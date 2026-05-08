from pathlib import Path

import pytest

from anthropic_news_mcp.fetchers.newsroom import _parse_newsroom_html
from anthropic_news_mcp.models import Category, Source

FIXTURE = Path(__file__).parent.parent / "fixtures" / "newsroom.html"


@pytest.fixture(scope="module")
def items():
    html = FIXTURE.read_text(encoding="utf-8")
    return _parse_newsroom_html(html)


def test_returns_items(items):
    assert len(items) >= 5


def test_capped_at_15(items):
    assert len(items) <= 15


def test_source_fields(items):
    for item in items:
        assert item.source == Source.ANTHROPIC
        assert item.source_key == "anthropic-newsroom"


def test_ids_are_stable_across_parses():
    html = FIXTURE.read_text(encoding="utf-8")
    first = {i.id for i in _parse_newsroom_html(html)}
    second = {i.id for i in _parse_newsroom_html(html)}
    assert first == second


def test_all_items_have_titles(items):
    for item in items:
        assert len(item.title) >= 3, f"Short title: {item.title!r}"


def test_all_items_have_urls(items):
    for item in items:
        url = str(item.url)
        assert "anthropic.com" in url, f"Unexpected URL: {url}"


def test_all_items_have_dates(items):

    for item in items:
        assert item.sort_at is not None
        if item.published_at is not None:
            assert item.published_at.tzinfo is not None
            # Dates should be within a reasonable range
            assert item.published_at.year >= 2024


def test_importance_is_3(items):
    for item in items:
        assert item.importance == 3


def test_no_duplicate_ids(items):
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


def test_sorted_newest_first(items):
    for a, b in zip(items, items[1:], strict=False):
        assert (a.sort_at or a.discovered_at) >= (b.sort_at or b.discovered_at)


def test_category_assigned(items):
    for item in items:
        assert len(item.category) >= 1
        for cat in item.category:
            assert cat in list(Category)
