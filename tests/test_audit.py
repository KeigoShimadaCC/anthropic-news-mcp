from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthropic_news_mcp.audit import main, run_audit
from anthropic_news_mcp.config import SourceConfig
from anthropic_news_mcp.models import Category, NewsItem, Source


class OkFetcher:
    async def fetch(self) -> list[NewsItem]:
        return [
            NewsItem(
                id="audit-ok",
                title="Audit success",
                summary="",
                url="https://anthropic.com/news/audit-ok",  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key="audit-ok",
                category=[Category.BUSINESS],
                published_at=datetime(2026, 5, 1, tzinfo=UTC),
                importance=1,
            )
        ]


class EmptyFetcher:
    async def fetch(self) -> list[NewsItem]:
        return []


class FailedFetcher:
    async def fetch(self) -> list[NewsItem]:
        raise RuntimeError("token=secret failure?api_key=secret")


@pytest.mark.asyncio
async def test_audit_reports_success_empty_and_failed(monkeypatch) -> None:
    registry = [
        SourceConfig("audit-ok", OkFetcher, 60, [Category.BUSINESS]),
        SourceConfig("anthropic-newsroom", EmptyFetcher, 60, [Category.BUSINESS]),
        SourceConfig("audit-fail", FailedFetcher, 60, [Category.BUSINESS]),
    ]
    monkeypatch.setattr("anthropic_news_mcp.audit.SOURCE_REGISTRY", registry)
    report = await run_audit()
    by_key = {source["key"]: source for source in report["sources"]}
    assert by_key["audit-ok"]["status"] == "ok"
    assert by_key["anthropic-newsroom"]["status"] == "warning"
    assert by_key["audit-fail"]["status"] == "failed"
    assert "?[redacted]" in by_key["audit-fail"]["error"]


def test_audit_json_and_strict_exit(monkeypatch, tmp_path: Path) -> None:
    registry = [SourceConfig("anthropic-newsroom", FailedFetcher, 60, [Category.BUSINESS])]
    monkeypatch.setattr("anthropic_news_mcp.audit.SOURCE_REGISTRY", registry)
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        "sys.argv",
        ["anthropic-news-audit", "--json", str(output), "--strict"],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert output.exists()
    assert "anthropic-newsroom" in output.read_text()
