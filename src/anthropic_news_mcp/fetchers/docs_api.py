"""Fetcher for Anthropic API release notes (platform.claude.com/docs)."""

import re
from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from ..http import get_client
from ..models import Category, DateConfidence, NewsItem, Source
from .base import Fetcher

_URL = "https://platform.claude.com/docs/en/release-notes/overview"
_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_LONG_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_DATE_RE = re.compile(
    rf"(?:({_LONG_MONTHS})|({_MONTHS}))\s+(\d{{1,2}}),?\s+(\d{{4}})",
    re.IGNORECASE,
)


def _parse_date(text: str) -> datetime | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    month_str = (m.group(1) or m.group(2)).strip()[:3]
    day = m.group(3)
    year = m.group(4)
    try:
        return datetime.strptime(f"{month_str} {day} {year}", "%b %d %Y").replace(tzinfo=UTC)
    except ValueError:
        return None


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_api_docs_html(html: str, limit: int = 10) -> list[NewsItem]:
    tree = HTMLParser(html)
    items: list[NewsItem] = []
    seen: set[str] = set()

    for h3 in tree.css("h3"):
        text = h3.text(strip=True)
        if not _DATE_RE.search(text):
            continue

        published_at = _parse_date(text)
        item_id = f"docs-api-{_slugify(text)}"
        if item_id in seen:
            continue
        seen.add(item_id)

        # Collect bullets from immediately following ul
        bullets: list[str] = []
        node = h3.next
        while node:
            if node.tag == "ul":
                for li in node.css("li"):
                    bullet = li.text(strip=True)
                    if bullet:
                        bullets.append(bullet)
                break
            if node.tag in ("h2", "h3"):
                break
            node = node.next

        summary = " · ".join(bullets[:3])[:400]
        title = f"API Release Notes: {text}"

        items.append(
            NewsItem(
                id=item_id,
                title=title,
                summary=summary,
                url=_URL,  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=ApiDocsFetcher.source_key,
                category=[Category.MODELS],
                published_at=published_at,
                date_confidence=DateConfidence.EXACT if published_at else DateConfidence.UNKNOWN,
                importance=2,
            )
        )
        if len(items) >= limit:
            break

    items.sort(key=lambda x: x.sort_at or x.discovered_at, reverse=True)
    return items[:limit]


class ApiDocsFetcher(Fetcher):
    source_key = "anthropic-docs-api"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
        return _parse_api_docs_html(resp.text)
