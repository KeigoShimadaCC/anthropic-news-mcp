"""Tests for content.py — text extraction, excerpt building, and fetch fallbacks."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.content import (
    _MAX_RESPONSE_BYTES,
    _MAX_STORED_CHARS,
    build_excerpts,
    content_hash,
    extract_text,
    fetch_content_detail,
    normalize_text,
)
from anthropic_news_mcp.models import (
    Category,
    ContentDetail,
    EvidenceTier,
    NewsItem,
    Source,
    SourceType,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    cache_mod.set_db_path(tmp_path / "test.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _item(url: str = "https://anthropic.com/news/test") -> NewsItem:
    return NewsItem(
        id="test-item-1",
        title="Claude 4 Released",
        summary="A major model release from Anthropic.",
        url=url,  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key="anthropic-newsroom",
        category=[Category.MODELS],
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        importance=3,
    )


class TestNormalizeText:
    def test_collapses_whitespace(self) -> None:
        assert normalize_text("hello   world\n\nfoo") == "hello world foo"

    def test_strips_edges(self) -> None:
        assert normalize_text("  hi  ") == "hi"


class TestContentHash:
    def test_deterministic(self) -> None:
        assert content_hash("hello") == content_hash("hello")

    def test_different_inputs_differ(self) -> None:
        assert content_hash("a") != content_hash("b")


class TestExtractText:
    def test_html_strips_tags(self) -> None:
        html = "<html><body><p>Hello <b>world</b></p></body></html>"
        result = extract_text(html, "text/html")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_html_removes_script_and_nav(self) -> None:
        html = "<html><body><nav>Skip</nav><p>Content</p><script>alert(1)</script></body></html>"
        result = extract_text(html, "text/html")
        assert "Content" in result
        assert "Skip" not in result
        assert "alert" not in result

    def test_plain_text_passthrough(self) -> None:
        result = extract_text("just text", "text/plain")
        assert result == "just text"

    def test_json_flattens_values(self) -> None:
        result = extract_text('{"title": "hello", "body": "world"}', "application/json")
        assert "hello" in result
        assert "world" in result

    def test_invalid_json_falls_back_to_normalized(self) -> None:
        result = extract_text("{not valid json}", "application/json")
        assert result == "{not valid json}"


class TestBuildExcerpts:
    def _detail(self, text: str) -> ContentDetail:
        return ContentDetail(
            item_id="test-item-1",
            url="https://anthropic.com/news/test",  # type: ignore[arg-type]
            normalized_text=text,
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            content_hash=content_hash(text),
            content_type="text/html",
            truncated=False,
        )

    def test_returns_excerpt_covering_query_term(self) -> None:
        text = "A" * 500 + " Sonnet " + "B" * 500
        detail = self._detail(text)
        excerpts = build_excerpts(
            _item(),
            detail,
            source_type=SourceType.OFFICIAL,
            evidence_tier=EvidenceTier.HIGH,
            query="Sonnet",
        )
        assert len(excerpts) >= 1
        assert "Sonnet" in excerpts[0].text

    def test_no_query_returns_first_window(self) -> None:
        detail = self._detail("Hello world " * 100)
        excerpts = build_excerpts(
            _item(),
            detail,
            source_type=SourceType.OFFICIAL,
            evidence_tier=EvidenceTier.HIGH,
        )
        assert len(excerpts) == 1
        assert excerpts[0].start_char == 0

    def test_excerpt_ids_are_stable(self) -> None:
        detail = self._detail("stable content")
        e1 = build_excerpts(
            _item(), detail, source_type=SourceType.OFFICIAL, evidence_tier=EvidenceTier.HIGH
        )
        e2 = build_excerpts(
            _item(), detail, source_type=SourceType.OFFICIAL, evidence_tier=EvidenceTier.HIGH
        )
        assert e1[0].evidence_id == e2[0].evidence_id

    def test_empty_text_returns_empty(self) -> None:
        detail = self._detail("")
        excerpts = build_excerpts(
            _item(), detail, source_type=SourceType.OFFICIAL, evidence_tier=EvidenceTier.HIGH
        )
        assert excerpts == []

    def test_respects_max_excerpts(self) -> None:
        text = "alpha beta gamma delta epsilon zeta " * 200
        detail = self._detail(text)
        excerpts = build_excerpts(
            _item(),
            detail,
            source_type=SourceType.OFFICIAL,
            evidence_tier=EvidenceTier.HIGH,
            query="alpha beta gamma",
            max_excerpts=2,
        )
        assert len(excerpts) <= 2


class TestFetchContentDetail:
    def _mock_response(
        self,
        body: str = "<html><body><p>Hello</p></body></html>",
        content_type: str = "text/html",
        status_code: int = 200,
        size: int | None = None,
    ) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = body
        resp.content = body.encode() if size is None else b"x" * size
        resp.headers = {"content-type": content_type}
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_fetches_and_extracts_html(self) -> None:
        resp = self._mock_response("<html><body><p>Anthropic news</p></body></html>")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)
        with patch("anthropic_news_mcp.content.get_client", return_value=mock_client):
            detail = await fetch_content_detail(_item())
        assert "Anthropic news" in detail.normalized_text
        assert detail.item_id == "test-item-1"
        assert not detail.truncated

    @pytest.mark.asyncio
    async def test_unsupported_content_type_falls_back_to_summary(self) -> None:
        resp = self._mock_response(b"binary".decode(), content_type="application/octet-stream")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)
        with patch("anthropic_news_mcp.content.get_client", return_value=mock_client):
            detail = await fetch_content_detail(_item())
        assert "Claude 4 Released" in detail.normalized_text
        assert any("unsupported content type" in w for w in detail.warnings)

    @pytest.mark.asyncio
    async def test_oversized_response_falls_back_to_summary(self) -> None:
        resp = self._mock_response(size=_MAX_RESPONSE_BYTES + 1)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)
        with patch("anthropic_news_mcp.content.get_client", return_value=mock_client):
            detail = await fetch_content_detail(_item())
        assert any("exceeds limit" in w for w in detail.warnings)
        assert "Claude 4 Released" in detail.normalized_text

    @pytest.mark.asyncio
    async def test_truncation_flag_set_for_long_text(self) -> None:
        long_body = f"<html><body><p>{'word ' * 20000}</p></body></html>"
        resp = self._mock_response(long_body)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)
        with patch("anthropic_news_mcp.content.get_client", return_value=mock_client):
            detail = await fetch_content_detail(_item())
        assert detail.truncated
        assert len(detail.normalized_text) <= _MAX_STORED_CHARS
