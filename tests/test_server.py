"""Server integration tests using FastMCP.call_tool()."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.models import Category, ContentDetail, NewsItem, Source


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
            published_at=datetime(2026, 5, i + 1, tzinfo=UTC),
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
    assert "anthropic-status" in keys
    assert "anthropic-engineering" in keys
    assert "anthropic-economic-index" in keys
    assert "anthropic-trust-policy" in keys
    assert "hn-anthropic" in keys
    assert "reddit-claude" in keys
    from anthropic_news_mcp.config import SOURCE_REGISTRY

    assert set(keys) == {s.key for s in SOURCE_REGISTRY}


@pytest.mark.asyncio
async def test_get_recent_updates_cached_items() -> None:
    _seed("anthropic-newsroom", n=3)
    data = await _call("get_recent_updates", {"sources": ["anthropic-newsroom"], "limit": 10})
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
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
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
            published_at=datetime(2026, 5, 2, tzinfo=UTC),
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
async def test_get_recent_updates_new_category_filter() -> None:
    items = [
        NewsItem(
            id="cat-ops",
            title="Status incident",
            summary="",
            url="https://status.claude.com/incidents/1",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-status",
            category=[Category.OPS],
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
            importance=3,
        )
    ]
    cache_mod.save_snapshot("anthropic-status", items, ttl_seconds=3600)
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-status"], "categories": ["ops"]},
    )
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "cat-ops"


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
    data = await _call("get_recent_updates", {"sources": ["anthropic-newsroom"], "limit": 2})
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
async def test_get_recent_updates_invalid_category_graceful() -> None:
    """Unknown category values must return an error dict, not raise an exception."""
    _seed("anthropic-newsroom", n=2)
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-newsroom"], "categories": ["not-a-real-category"]},
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "not-a-real-category" in data["error"]["message"]
    # Valid keys should be listed in the error
    assert "models" in data["error"]["message"]
    assert "ops" in data["error"]["message"]
    assert "engineering" in data["error"]["message"]
    assert "economics" in data["error"]["message"]


@pytest.mark.asyncio
async def test_get_recent_updates_new_source_key_from_seeded_cache() -> None:
    _seed("anthropic-engineering", n=1)
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-engineering"], "limit": 5},
    )
    assert len(data["items"]) == 1
    assert data["items"][0]["source_key"] == "anthropic-engineering"


@pytest.mark.asyncio
async def test_get_recent_updates_too_many_sources() -> None:
    """Passing more than 50 source keys must return a descriptive error."""
    data = await _call(
        "get_recent_updates",
        {"sources": [f"src-{i}" for i in range(51)]},
    )
    assert "error" in data


@pytest.mark.asyncio
async def test_get_recent_updates_unknown_source_key_returns_error() -> None:
    """Unknown source key must return an error, not a silent empty result."""
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-newsroom-typo"]},
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "anthropic-newsroom-typo" in data["error"]["message"]


@pytest.mark.asyncio
async def test_get_recent_updates_rejects_date_only_since() -> None:
    _seed("anthropic-newsroom", n=2)
    data = await _call(
        "get_recent_updates",
        {"sources": ["anthropic-newsroom"], "since": "2026-05-01"},
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "timezone-aware" in data["error"]["message"]


@pytest.mark.asyncio
async def test_get_recent_updates_rejects_bad_limit() -> None:
    data = await _call("get_recent_updates", {"limit": 0})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "limit must be greater than zero.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_search_updates_rejects_blank_query_and_bad_limit() -> None:
    data = await _call("search_updates", {"query": "   "})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "query must not be blank.",
        "details": {},
    }

    data = await _call("search_updates", {"query": "claude", "limit": -1})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "limit must be greater than zero.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_get_source_health_all_sources() -> None:
    from anthropic_news_mcp.config import SOURCE_REGISTRY

    data = await _call("get_source_health", {})
    returned_keys = {s["key"] for s in data["sources"]}
    configured_keys = {s.key for s in SOURCE_REGISTRY}
    assert configured_keys == returned_keys


def test_tool_contracts_have_annotations_and_output_schemas() -> None:
    from anthropic_news_mcp.server import mcp

    by_name = {tool.name: tool for tool in mcp._tool_manager.list_tools()}  # noqa: SLF001
    read_only_tools = [
        "ping",
        "list_sources",
        "get_recent_updates",
        "search_updates",
        "get_source_health",
        "get_update_detail",
        "search_web_sources",
        "get_timeline",
        "compare_updates",
        "build_digest_context",
        "get_research_session",
        "evaluate_claims",
    ]
    for name in read_only_tools:
        tool = by_name[name]
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.fn_metadata.output_schema is not None

    for name in ["create_research_session", "save_research_note", "save_research_report"]:
        tool = by_name[name]
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.destructiveHint is False
        assert tool.fn_metadata.output_schema is not None

    assert by_name["get_recent_updates"].annotations.openWorldHint is True
    assert by_name["search_updates"].annotations.openWorldHint is True
    assert by_name["get_update_detail"].annotations.openWorldHint is True
    assert by_name["create_research_session"].annotations.readOnlyHint is False
    assert "limit" in by_name["get_recent_updates"].parameters["properties"]


@pytest.mark.asyncio
async def test_resources_and_prompts_registered() -> None:
    from anthropic_news_mcp.server import mcp

    resources = {str(resource.uri) for resource in mcp._resource_manager.list_resources()}  # noqa: SLF001
    templates = {template.uri_template for template in mcp._resource_manager.list_templates()}  # noqa: SLF001
    prompts = {prompt.name for prompt in mcp._prompt_manager.list_prompts()}  # noqa: SLF001

    assert "anthropic-news://sources" in resources
    assert "anthropic-news://health" in resources
    assert "anthropic-news://source/{source_key}/latest" in templates
    assert "anthropic-news://evidence/{evidence_id}" in templates
    assert "anthropic-news://session/{session_id}" in templates
    assert {
        "latest_update_digest",
        "source_health_report",
        "weekly_category_digest",
        "generate_digest",
        "verify_claims_against_evidence",
        "research_session_brief",
    }.issubset(prompts)

    source_resource = await mcp._resource_manager.get_resource("anthropic-news://sources")  # noqa: SLF001
    assert source_resource is not None
    source_payload = json.loads(await source_resource.read())
    assert "anthropic-newsroom" in {source["key"] for source in source_payload["sources"]}

    _seed("anthropic-newsroom", n=1)
    latest_resource = await mcp._resource_manager.get_resource(  # noqa: SLF001
        "anthropic-news://source/anthropic-newsroom/latest"
    )
    assert latest_resource is not None
    latest_payload = json.loads(await latest_resource.read())
    assert latest_payload["items"][0]["source_key"] == "anthropic-newsroom"

    messages = await mcp._prompt_manager.render_prompt(  # noqa: SLF001
        "weekly_category_digest",
        {"category": "models", "since": "2026-05-01T00:00:00Z"},
    )
    assert "get_recent_updates" in messages[0].content.text


@pytest.mark.asyncio
async def test_research_detail_search_session_and_claim_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _seed("anthropic-newsroom", n=1)[0]

    async def fake_fetch_content_detail(news_item: NewsItem) -> ContentDetail:
        return ContentDetail(
            item_id=news_item.id,
            url=news_item.url,
            normalized_text="Claude Code shipped a research feature with citations and evidence.",
            retrieved_at=datetime(2026, 5, 4, tzinfo=UTC),
            content_hash="hash1",
            content_type="text/html",
        )

    monkeypatch.setattr(
        "anthropic_news_mcp.research.fetch_content_detail", fake_fetch_content_detail
    )

    detail = await _call("get_update_detail", {"id": item.id, "excerpt_query": "citations"})
    assert detail["item"]["id"] == item.id
    assert detail["detail"]["content_hash"] == "hash1"
    assert detail["excerpts"]
    evidence_id = detail["excerpts"][0]["evidence_id"]

    search = await _call(
        "search_web_sources",
        {"query": "citations", "sources": ["anthropic-newsroom"], "refresh": False},
    )
    assert search["items"][0]["id"] == item.id

    timeline = await _call(
        "get_timeline",
        {
            "topic": "citations",
            "since": "2026-05-01T00:00:00Z",
            "sources": ["anthropic-newsroom"],
        },
    )
    assert timeline["groups"]

    session = await _call(
        "create_research_session",
        {"title": "Citation research", "topic": "citations"},
    )
    session_id = session["session"]["session_id"]
    note = await _call(
        "save_research_note",
        {"session_id": session_id, "text": "Check citation support", "evidence_ids": [evidence_id]},
    )
    assert note["note"]["follow_up"] is False
    report = await _call(
        "save_research_report",
        {
            "session_id": session_id,
            "title": "Digest",
            "markdown": "Claude Code shipped citations.",
            "evidence_ids": [evidence_id],
        },
    )
    assert report["report"]["title"] == "Digest"
    session_payload = await _call("get_research_session", {"session_id": session_id})
    assert session_payload["notes"]
    assert session_payload["reports"]

    evaluation = await _call(
        "evaluate_claims",
        {"claims": ["Claude Code shipped citations"], "evidence_ids": [evidence_id]},
    )
    assert evaluation["results"][0]["support"] in {"strong_support", "weak_support"}


@pytest.mark.asyncio
async def test_compare_updates_returns_new_items() -> None:
    _seed("anthropic-newsroom", n=2)
    data = await _call("compare_updates", {})
    assert "new_items" in data
    assert "changed_items" in data
    assert "disappeared_items" in data
    assert len(data["new_items"]) == 2


@pytest.mark.asyncio
async def test_compare_updates_since_filters_old_items() -> None:
    _seed("anthropic-newsroom", n=2)
    data = await _call("compare_updates", {"since": "2099-01-01T00:00:00Z"})
    assert data["new_items"] == []
    assert data["changed_items"] == []


@pytest.mark.asyncio
async def test_build_digest_context_returns_timeline() -> None:
    _seed("anthropic-newsroom", n=2)
    data = await _call(
        "build_digest_context",
        {"topic": "anthropic", "since": "2026-01-01T00:00:00Z"},
    )
    assert "timeline" in data
    assert data["topic"] == "anthropic"
    assert "instructions" in data


@pytest.mark.asyncio
async def test_search_web_sources_rejects_inverted_time_range() -> None:
    data = await _call(
        "search_web_sources",
        {
            "query": "claude",
            "since": "2026-05-03T00:00:00Z",
            "until": "2026-05-01T00:00:00Z",
        },
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "since" in data["error"]["message"]


@pytest.mark.asyncio
async def test_search_web_sources_rejects_invalid_source_type_and_importance() -> None:
    data = await _call(
        "search_web_sources",
        {"query": "claude", "source_types": ["not-real"]},
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "Unknown source types" in data["error"]["message"]

    data = await _call(
        "search_web_sources",
        {"query": "claude", "importance": [4]},
    )
    assert data["error"] == {
        "code": "invalid_request",
        "message": "importance values must be 1, 2, or 3.",
        "details": {"invalid": [4]},
    }


@pytest.mark.asyncio
async def test_get_update_detail_rejects_blank_id_and_bad_limit() -> None:
    data = await _call("get_update_detail", {"id": "   "})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "id must not be blank.",
        "details": {},
    }

    data = await _call("get_update_detail", {"id": "x", "max_chars": 0})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "limit must be greater than zero.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_research_session_tools_validate_blank_and_unknown_inputs() -> None:
    data = await _call("create_research_session", {"title": "   "})
    assert data["error"] == {
        "code": "invalid_request",
        "message": "title must not be blank.",
        "details": {},
    }

    data = await _call("save_research_note", {"session_id": "missing", "text": "note"})
    assert data["error"]["message"] == "Unknown research session: missing"

    data = await _call(
        "save_research_report",
        {"session_id": "missing", "title": "Report", "markdown": "body"},
    )
    assert data["error"]["message"] == "Unknown research session: missing"

    data = await _call("get_research_session", {"session_id": "   "})
    assert data["error"]["message"] == "session_id must not be blank."

    data = await _call("evaluate_claims", {"claims": ["   "]})
    assert data["error"]["message"] == "claims must include at least one non-blank claim."


@pytest.mark.asyncio
async def test_build_digest_context_rejects_inverted_time_range() -> None:
    data = await _call(
        "build_digest_context",
        {
            "topic": "claude",
            "since": "2026-05-03T00:00:00Z",
            "until": "2026-05-01T00:00:00Z",
        },
    )
    assert data["error"] == {
        "code": "invalid_request",
        "message": "since must be earlier than until.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_get_timeline_rejects_inverted_time_range() -> None:
    data = await _call(
        "get_timeline",
        {
            "topic": "claude",
            "since": "2026-05-03T00:00:00Z",
            "until": "2026-05-01T00:00:00Z",
        },
    )
    assert "error" in data
    assert data["error"]["code"] == "invalid_request"
    assert "since" in data["error"]["message"]
