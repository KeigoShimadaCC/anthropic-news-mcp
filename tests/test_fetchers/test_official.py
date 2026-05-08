import json
from pathlib import Path

from anthropic_news_mcp.fetchers.official import (
    _BUSINESS_TERMS,
    _TRUST_TERMS,
    _filter_items,
    parse_anthropic_listing_html,
    parse_release_notes_html,
    parse_status_payloads,
)
from anthropic_news_mcp.models import Category

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_status_operational_has_no_rollup_and_maps_impacts() -> None:
    items = parse_status_payloads(
        summary=json.loads((FIXTURES / "status_operational.json").read_text()),
        incidents=json.loads((FIXTURES / "status_incidents.json").read_text()),
        scheduled=json.loads((FIXTURES / "status_scheduled.json").read_text()),
    )
    assert len(items) == 3
    assert all(item.category == [Category.OPS] for item in items)
    assert {item.title: item.importance for item in items}[
        "Elevated API errors"
    ] == 3
    assert {item.title: item.importance for item in items}[
        "Minor dashboard delay"
    ] == 2
    assert {item.title: item.importance for item in items}[
        "Scheduled maintenance"
    ] == 1


def test_status_non_operational_adds_rollup() -> None:
    items = parse_status_payloads(
        summary={"status": {"indicator": "minor", "description": "Partial outage"}},
        incidents={"incidents": []},
        scheduled={"scheduled_maintenances": []},
    )
    assert len(items) == 1
    assert items[0].title == "Claude Status: Partial outage"
    assert items[0].importance == 2


def test_research_listing_categories_and_ordinal_date() -> None:
    html = (FIXTURES / "research.html").read_text()
    items = parse_anthropic_listing_html(
        html,
        source_key="anthropic-research",
        id_prefix="research",
        page_url="https://www.anthropic.com/research",
        default_categories=[Category.RESEARCH],
        href_contains="/research/",
    )
    econ = next(item for item in items if "economic impact" in item.title)
    assert econ.published_at.year == 2025
    assert econ.published_at.month == 2
    assert econ.published_at.day == 24
    assert Category.ECONOMICS in econ.category
    assert Category.POLICY in next(item for item in items if "trustworthy" in item.title).category


def test_engineering_listing_assigns_engineering_category() -> None:
    html = (FIXTURES / "engineering.html").read_text()
    items = parse_anthropic_listing_html(
        html,
        source_key="anthropic-engineering",
        id_prefix="engineering",
        page_url="https://www.anthropic.com/engineering",
        default_categories=[Category.ENGINEERING],
        href_contains="/engineering/",
    )
    assert len(items) == 2
    assert all(Category.ENGINEERING in item.category for item in items)
    assert items[0].title == "Reliable evals at scale"


def test_release_notes_parse_full_and_month_section_dates() -> None:
    html = (FIXTURES / "docs_claude_apps.html").read_text()
    items = parse_release_notes_html(
        html,
        source_key="anthropic-docs-claude-apps",
        id_prefix="docs-claude-apps",
        url="https://docs.claude.com/en/release-notes/claude-apps",
        categories=[Category.MODELS],
        title_prefix="Claude Apps Release Notes",
    )
    assert len(items) == 2
    assert items[0].published_at.day == 24
    assert items[1].published_at.day == 18
    assert "Claude Desktop" in items[0].summary


def test_docs_and_support_release_notes_have_stable_ids() -> None:
    for fixture, source_key, prefix, url, categories, title_prefix in [
        (
            "docs_system_prompts.html",
            "anthropic-docs-system-prompts",
            "docs-system-prompts",
            "https://docs.claude.com/en/release-notes/system-prompts",
            [Category.POLICY],
            "System Prompt Release Notes",
        ),
        (
            "support_release_notes.html",
            "anthropic-support-release-notes",
            "support-release-notes",
            "https://support.claude.com/en/articles/12138966-release-notes",
            [Category.MODELS],
            "Claude Help Center Release Notes",
        ),
    ]:
        html = (FIXTURES / fixture).read_text()
        first = parse_release_notes_html(
            html,
            source_key=source_key,
            id_prefix=prefix,
            url=url,
            categories=categories,
            title_prefix=title_prefix,
        )
        second = parse_release_notes_html(
            html,
            source_key=source_key,
            id_prefix=prefix,
            url=url,
            categories=categories,
            title_prefix=title_prefix,
        )
        assert [item.id for item in first] == [item.id for item in second]
        assert first


def test_business_and_trust_filters_rekey_official_items() -> None:
    html = (FIXTURES / "newsroom_filters.html").read_text()
    items = parse_anthropic_listing_html(
        html,
        source_key="anthropic-newsroom",
        id_prefix="newsroom",
        page_url="https://www.anthropic.com/news",
        default_categories=[Category.BUSINESS],
        href_contains="/news/",
    )
    business = _filter_items(
        items,
        source_key="anthropic-business-infrastructure",
        id_prefix="business-infra",
        terms=_BUSINESS_TERMS,
        categories=[Category.BUSINESS],
    )
    trust = _filter_items(
        items,
        source_key="anthropic-trust-policy",
        id_prefix="trust-policy",
        terms=_TRUST_TERMS,
        categories=[Category.POLICY],
    )
    assert [item.source_key for item in business] == [
        "anthropic-business-infrastructure"
    ]
    assert [item.source_key for item in trust] == ["anthropic-trust-policy"]
