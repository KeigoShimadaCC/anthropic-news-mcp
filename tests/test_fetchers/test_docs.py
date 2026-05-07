from pathlib import Path

import pytest

from anthropic_news_mcp.fetchers.docs_api import _parse_api_docs_html
from anthropic_news_mcp.fetchers.docs_claude_code import _parse_changelog_markdown
from anthropic_news_mcp.models import Category, Source

CC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "docs_claude_code_raw.md"
API_FIXTURE = Path(__file__).parent.parent / "fixtures" / "docs_api.html"


class TestClaudeCodeDocs:
    @pytest.fixture(scope="class")
    def items(self):
        text = CC_FIXTURE.read_text(encoding="utf-8")
        return _parse_changelog_markdown(text)

    def test_returns_items(self, items):
        assert len(items) >= 5

    def test_capped_at_default_limit(self, items):
        assert len(items) <= 10

    def test_respects_custom_limit(self):
        text = CC_FIXTURE.read_text(encoding="utf-8")
        items = _parse_changelog_markdown(text, limit=3)
        assert len(items) == 3

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.ANTHROPIC
            assert item.source_key == "anthropic-docs-claude-code"

    def test_category_is_claude_code(self, items):
        for item in items:
            assert Category.CLAUDE_CODE in item.category

    def test_ids_are_stable(self):
        text = CC_FIXTURE.read_text(encoding="utf-8")
        first = {i.id for i in _parse_changelog_markdown(text)}
        second = {i.id for i in _parse_changelog_markdown(text)}
        assert first == second

    def test_all_have_titles(self, items):
        for item in items:
            assert "Claude Code" in item.title

    def test_summaries_populated(self, items):
        for item in items:
            assert len(item.summary) > 0

    def test_no_duplicate_ids(self, items):
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_importance_is_2(self, items):
        for item in items:
            assert item.importance == 2


class TestApiDocs:
    @pytest.fixture(scope="class")
    def items(self):
        html = API_FIXTURE.read_text(encoding="utf-8")
        return _parse_api_docs_html(html)

    def test_returns_items(self, items):
        assert len(items) >= 5

    def test_capped_at_default_limit(self, items):
        assert len(items) <= 10

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.ANTHROPIC
            assert item.source_key == "anthropic-docs-api"

    def test_category_is_models(self, items):
        for item in items:
            assert Category.MODELS in item.category

    def test_all_have_dates(self, items):
        for item in items:
            assert item.published_at.year >= 2025

    def test_sorted_newest_first(self, items):
        for a, b in zip(items, items[1:]):
            assert a.published_at >= b.published_at

    def test_ids_are_stable(self):
        html = API_FIXTURE.read_text(encoding="utf-8")
        first = {i.id for i in _parse_api_docs_html(html)}
        second = {i.id for i in _parse_api_docs_html(html)}
        assert first == second

    def test_no_duplicate_ids(self, items):
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_importance_is_2(self, items):
        for item in items:
            assert item.importance == 2
