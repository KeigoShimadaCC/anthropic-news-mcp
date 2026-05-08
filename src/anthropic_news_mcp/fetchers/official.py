"""Official Anthropic source fetchers and shared parsers."""

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Literal, cast

from selectolax.parser import HTMLParser

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_BASE = "https://www.anthropic.com"
_SHORT_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_LONG_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_DATE_RE = re.compile(
    rf"(?:({_LONG_MONTHS})|({_SHORT_MONTHS}))\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)
_MONTH_SECTION_RE = re.compile(rf"^({_LONG_MONTHS})\s+(\d{{4}})$", re.IGNORECASE)

_SECTION_TO_CATEGORY: dict[str, list[Category]] = {
    "policy": [Category.POLICY],
    "research": [Category.RESEARCH],
    "economic research": [Category.ECONOMICS, Category.RESEARCH],
    "engineering": [Category.ENGINEERING],
    "product": [Category.MODELS],
    "products": [Category.MODELS],
    "announcements": [Category.BUSINESS],
    "announcement": [Category.BUSINESS],
    "company": [Category.BUSINESS],
    "safety": [Category.POLICY],
    "news": [Category.BUSINESS],
    "changelog": [Category.CLAUDE_CODE],
}

_BUSINESS_TERMS = (
    "compute",
    "infrastructure",
    "partnership",
    "partner",
    "funding",
    "investment",
    "investor",
    "enterprise",
    "customer",
    "revenue",
    "demand",
    "cloud",
    "amazon",
    "aws",
    "google cloud",
    "microsoft",
    "datacenter",
    "data center",
)
_TRUST_TERMS = (
    "responsible scaling",
    "rsp",
    "safety",
    "policy",
    "trust",
    "transparency",
    "red team",
    "red-team",
    "compliance",
    "safeguard",
    "preparedness",
    "alignment",
    "security",
    "misuse",
)


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _parse_date(text: str, default_day: int = 1) -> datetime:
    m = _DATE_RE.search(text)
    if m:
        month = (m.group(1) or m.group(2)).strip()[:3]
        day = m.group(3)
        year = m.group(4)
        try:
            return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").replace(tzinfo=UTC)
        except ValueError:
            pass

    section = _MONTH_SECTION_RE.search(text.strip())
    if section:
        month = section.group(1)[:3]
        year = section.group(2)
        try:
            return datetime.strptime(f"{month} {default_day} {year}", "%b %d %Y").replace(
                tzinfo=UTC
            )
        except ValueError:
            pass

    return datetime.now(tz=UTC)


def _categories_from_text(text: str, default: list[Category]) -> list[Category]:
    lower = text.lower()
    if "economic research" in lower or "economic index" in lower:
        return [Category.ECONOMICS, Category.RESEARCH]
    for key, categories in _SECTION_TO_CATEGORY.items():
        if re.search(rf"\b{re.escape(key)}\b", lower):
            return categories
    return default


def _title_from_anchor(anchor: Any, full_text: str) -> str:
    for tag in ("h1", "h2", "h3", "h4", "h5"):
        node = next((c for c in anchor.iter() if c.tag == tag and c.text(strip=True)), None)
        if node:
            return str(node.text(strip=True))

    clean = _DATE_RE.sub("", full_text)
    clean = re.sub(
        r"\b(Announcements?|Products?|Research|Economic Research|Policy|News|Safety|Company|Changelog|Engineering)\b",
        "",
        clean,
        flags=re.I,
    ).strip()
    return clean.splitlines()[0].strip()[:160] if clean else ""


def parse_anthropic_listing_html(
    html: str,
    *,
    source_key: str,
    id_prefix: str,
    page_url: str,
    default_categories: list[Category],
    href_contains: str | None = None,
    limit: int = 20,
    importance: Literal[1, 2, 3] | None = None,
) -> list[NewsItem]:
    """Parse Anthropic card/listing pages such as /news, /research, and /engineering."""
    tree = HTMLParser(html)
    items: list[NewsItem] = []
    seen: set[str] = set()

    for a in tree.css("a[href]"):
        href = str(a.attributes.get("href") or "")
        if href_contains and href_contains not in href:
            continue
        if href in {"", "/", page_url}:
            continue

        text = a.text(strip=True)
        if len(text) < 5:
            continue

        url = href if href.startswith("http") else f"{_BASE}{href}"
        item_id = _stable_id(id_prefix, url)
        if item_id in seen:
            continue
        seen.add(item_id)

        title = _title_from_anchor(a, text)
        if not title:
            continue

        summary_node = next((c for c in a.iter() if c.tag == "p" and c.text(strip=True)), None)
        summary = summary_node.text(strip=True)[:400] if summary_node else ""
        categories = _categories_from_text(text, default_categories)

        items.append(
            NewsItem(
                id=item_id,
                title=title,
                summary=summary,
                url=url,  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=source_key,
                category=categories,
                published_at=_parse_date(text),
                importance=importance
                if importance is not None
                else (3 if Category.POLICY in categories else 2),
            )
        )

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items[:limit]


def _heading_level(tag: str | None) -> int:
    return int(tag[1]) if tag and re.fullmatch(r"h[1-6]", tag) else 0


def parse_release_notes_html(
    html: str,
    *,
    source_key: str,
    id_prefix: str,
    url: str,
    categories: list[Category],
    title_prefix: str,
    limit: int = 20,
) -> list[NewsItem]:
    """Parse docs/help release notes with date headings and nearby bullets."""
    tree = HTMLParser(html)
    items: list[NewsItem] = []
    current_month = ""
    seen: set[str] = set()

    for heading in tree.css("h1,h2,h3,h4"):
        text = heading.text(strip=True)
        if _MONTH_SECTION_RE.match(text):
            current_month = text
            continue

        date_text = text
        if not _DATE_RE.search(date_text) and current_month:
            day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", text)
            if day:
                month = _MONTH_SECTION_RE.match(current_month)
                if month:
                    date_text = f"{month.group(1)} {day.group(1)} {month.group(2)}"
        if not _DATE_RE.search(date_text):
            continue

        level = _heading_level(heading.tag)
        bullets: list[str] = []
        node = heading.next
        while node:
            if _heading_level(node.tag) and _heading_level(node.tag) <= level:
                break
            if node.tag == "ul":
                for li in node.css("li"):
                    bullet = li.text(strip=True)
                    if bullet:
                        bullets.append(bullet)
            elif node.tag == "li":
                bullet = node.text(strip=True)
                if bullet:
                    bullets.append(bullet)
            elif node.tag == "p" and node.text(strip=True) and not bullets:
                bullets.append(node.text(strip=True))
            node = node.next

        item_id = f"{id_prefix}-{re.sub(r'[^a-z0-9]+', '-', date_text.lower()).strip('-')}"
        if item_id in seen:
            continue
        seen.add(item_id)

        summary = " · ".join(bullets[:3])[:400]
        items.append(
            NewsItem(
                id=item_id,
                title=f"{title_prefix}: {text}",
                summary=summary,
                url=url,  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=source_key,
                category=categories,
                published_at=_parse_date(date_text),
                importance=2,
            )
        )
        if len(items) >= limit:
            break

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items[:limit]


def _filter_items(
    items: Iterable[NewsItem],
    *,
    source_key: str,
    id_prefix: str,
    terms: tuple[str, ...],
    categories: list[Category],
) -> list[NewsItem]:
    filtered: list[NewsItem] = []
    for item in items:
        haystack = f"{item.title} {item.summary} {' '.join(item.tags)}".lower()
        if not any(term in haystack for term in terms):
            continue
        filtered.append(
            item.model_copy(
                update={
                    "id": _stable_id(id_prefix, str(item.url)),
                    "source_key": source_key,
                    "category": list(dict.fromkeys([*categories, *item.category])),
                    "importance": max(item.importance, 2),
                }
            )
        )
    return filtered


class ResearchFetcher(Fetcher):
    source_key = "anthropic-research"
    url = "https://www.anthropic.com/research"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return parse_anthropic_listing_html(
            resp.text,
            source_key=self.source_key,
            id_prefix="research",
            page_url=self.url,
            default_categories=[Category.RESEARCH],
            href_contains="/research/",
            limit=30,
        )


class EngineeringFetcher(Fetcher):
    source_key = "anthropic-engineering"
    url = "https://www.anthropic.com/engineering"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return parse_anthropic_listing_html(
            resp.text,
            source_key=self.source_key,
            id_prefix="engineering",
            page_url=self.url,
            default_categories=[Category.ENGINEERING],
            href_contains="/engineering/",
            limit=30,
        )


class ClaudeAppsDocsFetcher(Fetcher):
    source_key = "anthropic-docs-claude-apps"
    url = "https://docs.claude.com/en/release-notes/claude-apps"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return parse_release_notes_html(
            resp.text,
            source_key=self.source_key,
            id_prefix="docs-claude-apps",
            url=self.url,
            categories=[Category.MODELS],
            title_prefix="Claude Apps Release Notes",
        )


class SystemPromptsDocsFetcher(Fetcher):
    source_key = "anthropic-docs-system-prompts"
    url = "https://docs.claude.com/en/release-notes/system-prompts"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return parse_release_notes_html(
            resp.text,
            source_key=self.source_key,
            id_prefix="docs-system-prompts",
            url=self.url,
            categories=[Category.POLICY],
            title_prefix="System Prompt Release Notes",
        )


class SupportReleaseNotesFetcher(Fetcher):
    source_key = "anthropic-support-release-notes"
    url = "https://support.claude.com/en/articles/12138966-release-notes"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return parse_release_notes_html(
            resp.text,
            source_key=self.source_key,
            id_prefix="support-release-notes",
            url=self.url,
            categories=[Category.MODELS],
            title_prefix="Claude Help Center Release Notes",
        )


class EconomicIndexFetcher(Fetcher):
    source_key = "anthropic-economic-index"
    index_url = "https://www.anthropic.com/economic-index"
    research_url = "https://www.anthropic.com/research"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            index_resp = await client.get(self.index_url)
            index_resp.raise_for_status()
            research_resp = await client.get(self.research_url)
            research_resp.raise_for_status()

        index_items = parse_anthropic_listing_html(
            index_resp.text,
            source_key=self.source_key,
            id_prefix="economic-index",
            page_url=self.index_url,
            default_categories=[Category.ECONOMICS],
            limit=10,
        )
        research_items = parse_anthropic_listing_html(
            research_resp.text,
            source_key=self.source_key,
            id_prefix="economic-research",
            page_url=self.research_url,
            default_categories=[Category.RESEARCH],
            href_contains="/research/",
            limit=30,
        )
        items = [
            *index_items,
            *[
                item.model_copy(
                    update={
                        "category": [Category.ECONOMICS, Category.RESEARCH],
                        "source_key": self.source_key,
                    }
                )
                for item in research_items
                if Category.ECONOMICS in item.category
                or "economic" in f"{item.title} {item.summary}".lower()
            ],
        ]
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:20]


class BusinessInfrastructureFetcher(Fetcher):
    source_key = "anthropic-business-infrastructure"
    url = "https://www.anthropic.com/news"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        items = parse_anthropic_listing_html(
            resp.text,
            source_key="anthropic-newsroom",
            id_prefix="newsroom",
            page_url=self.url,
            default_categories=[Category.BUSINESS],
            href_contains="/news/",
            limit=50,
        )
        return _filter_items(
            items,
            source_key=self.source_key,
            id_prefix="business-infra",
            terms=_BUSINESS_TERMS,
            categories=[Category.BUSINESS],
        )[:20]


class TrustPolicyFetcher(Fetcher):
    source_key = "anthropic-trust-policy"
    news_url = "https://www.anthropic.com/news"
    research_url = "https://www.anthropic.com/research"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            news_resp = await client.get(self.news_url)
            news_resp.raise_for_status()
            research_resp = await client.get(self.research_url)
            research_resp.raise_for_status()
        news_items = parse_anthropic_listing_html(
            news_resp.text,
            source_key="anthropic-newsroom",
            id_prefix="newsroom",
            page_url=self.news_url,
            default_categories=[Category.BUSINESS],
            href_contains="/news/",
            limit=50,
        )
        research_items = parse_anthropic_listing_html(
            research_resp.text,
            source_key="anthropic-research",
            id_prefix="research",
            page_url=self.research_url,
            default_categories=[Category.RESEARCH],
            href_contains="/research/",
            limit=50,
        )
        items = _filter_items(
            [*news_items, *research_items],
            source_key=self.source_key,
            id_prefix="trust-policy",
            terms=_TRUST_TERMS,
            categories=[Category.POLICY],
        )
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:25]


def parse_status_payloads(
    *,
    summary: dict[str, Any] | None = None,
    incidents: dict[str, Any] | None = None,
    scheduled: dict[str, Any] | None = None,
    source_key: str = "anthropic-status",
) -> list[NewsItem]:
    items: list[NewsItem] = []

    status = cast(dict[str, object], (summary or {}).get("status", {}))
    indicator = str(status.get("indicator") or "")
    description = str(status.get("description") or "")
    if indicator and indicator != "none":
        items.append(
            NewsItem(
                id=f"status-rollup-{indicator}",
                title=f"Claude Status: {description or indicator}",
                summary=description,
                url="https://status.claude.com/",  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=source_key,
                category=[Category.OPS],
                published_at=datetime.now(tz=UTC),
                importance=_impact_to_importance(indicator),
                tags=["status", indicator],
            )
        )

    for incident in (incidents or {}).get("incidents", []):
        items.append(_status_item(incident, source_key=source_key, kind="incident"))

    for maintenance in (scheduled or {}).get("scheduled_maintenances", []):
        items.append(_status_item(maintenance, source_key=source_key, kind="maintenance"))

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items


def _impact_to_importance(impact: str | None) -> Literal[1, 2, 3]:
    value = (impact or "none").lower()
    if value in {"critical", "major"}:
        return 3
    if value == "minor":
        return 2
    return 1


def _status_item(payload: dict[str, Any], *, source_key: str, kind: str) -> NewsItem:
    native_id = str(payload.get("id") or payload.get("shortlink") or payload.get("name"))
    impact = str(payload.get("impact") or "none")
    timestamp = (
        payload.get("started_at")
        or payload.get("scheduled_for")
        or payload.get("created_at")
        or payload.get("updated_at")
    )
    published_at = _parse_iso_datetime(str(timestamp)) if timestamp else datetime.now(tz=UTC)
    status = payload.get("status", "")
    summary = payload.get("impact_override") or payload.get("body") or status or ""
    url = payload.get("shortlink") or payload.get("url") or "https://status.claude.com/"
    return NewsItem(
        id=f"status-{kind}-{native_id}",
        title=str(payload.get("name") or f"Claude status {kind}"),
        summary=str(summary)[:400],
        url=url,  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key=source_key,
        category=[Category.OPS],
        published_at=published_at,
        importance=_impact_to_importance(impact),
        tags=["status", kind, impact, str(status)],
    )


def _parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=UTC)


class StatusFetcher(Fetcher):
    source_key = "anthropic-status"
    base_url = "https://status.claude.com/api/v2"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            summary_resp = await client.get(f"{self.base_url}/summary.json")
            summary_resp.raise_for_status()
            incidents_resp = await client.get(f"{self.base_url}/incidents.json")
            incidents_resp.raise_for_status()
            scheduled_resp = await client.get(
                f"{self.base_url}/scheduled-maintenances/upcoming.json"
            )
            scheduled_resp.raise_for_status()
        return parse_status_payloads(
            summary=summary_resp.json(),
            incidents=incidents_resp.json(),
            scheduled=scheduled_resp.json(),
            source_key=self.source_key,
        )
