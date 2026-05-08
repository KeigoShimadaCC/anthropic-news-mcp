import re
from datetime import UTC, datetime

from ..http import get_client
from ..models import Category, NewsItem
from .base import Fetcher
from .official import parse_anthropic_listing_html

_URL = "https://www.anthropic.com/news"
_BASE = "https://www.anthropic.com"

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_RE = re.compile(rf"({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})")
_SECTION_RE = re.compile(
    r"\b(Announcements?|Products?|Research|Policy|News|Safety|Company|Changelog)\b",
    re.I,
)

_SECTION_TO_CATEGORY: dict[str, list[Category]] = {
    "policy": [Category.POLICY],
    "research": [Category.RESEARCH],
    "product": [Category.MODELS],
    "products": [Category.MODELS],
    "announcements": [Category.BUSINESS],
    "announcement": [Category.BUSINESS],
    "company": [Category.BUSINESS],
    "safety": [Category.POLICY],
    "news": [Category.BUSINESS],
    "changelog": [Category.CLAUDE_CODE],
}


def _parse_date(text: str) -> datetime:
    m = _DATE_RE.search(text)
    if not m:
        return datetime.now(tz=UTC)
    try:
        return datetime.strptime(m.group(0).replace(",", ""), "%b %d %Y").replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(tz=UTC)


def _parse_section(text: str) -> list[Category]:
    m = _SECTION_RE.search(text)
    if not m:
        return [Category.BUSINESS]
    return _SECTION_TO_CATEGORY.get(m.group(1).lower(), [Category.BUSINESS])


def _parse_newsroom_html(html: str) -> list[NewsItem]:
    return parse_anthropic_listing_html(
        html,
        source_key=NewsroomFetcher.source_key,
        id_prefix="newsroom",
        page_url=_URL,
        default_categories=[Category.BUSINESS],
        href_contains="/news/",
        limit=15,
        importance=3,
    )


class NewsroomFetcher(Fetcher):
    source_key = "anthropic-newsroom"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
        return _parse_newsroom_html(resp.text)
