import hashlib
import re
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

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
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.strptime(m.group(0).replace(",", ""), "%b %d %Y").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return datetime.now(tz=timezone.utc)


def _parse_section(text: str) -> list[Category]:
    m = _SECTION_RE.search(text)
    if not m:
        return [Category.BUSINESS]
    return _SECTION_TO_CATEGORY.get(m.group(1).lower(), [Category.BUSINESS])


def _make_id(href: str) -> str:
    digest = hashlib.sha1(href.encode()).hexdigest()[:16]
    return f"newsroom-{digest}"


def _parse_newsroom_html(html: str) -> list[NewsItem]:
    tree = HTMLParser(html)
    items: list[NewsItem] = []
    seen: set[str] = set()

    for a in tree.css("a[href]"):
        href: str = a.attributes.get("href", "")
        if "/news/" not in href or href == "/news":
            continue
        text = a.text(strip=True)
        if len(text) < 5:
            continue

        item_id = _make_id(href)
        if item_id in seen:
            continue
        seen.add(item_id)

        url = href if href.startswith("http") else f"{_BASE}{href}"
        published_at = _parse_date(text)
        categories = _parse_section(text)

        # Extract title: prefer h2/h3/h4/span children
        title_node = next(
            (
                c
                for c in a.iter()
                if c.tag in ("h2", "h3", "h4", "h5", "span") and c.text(strip=True)
            ),
            None,
        )
        title = title_node.text(strip=True) if title_node else ""

        if not title:
            # Fall back: strip date+section from full text
            clean = _DATE_RE.sub("", text)
            clean = _SECTION_RE.sub("", clean).strip()
            # First line is title
            title = clean.splitlines()[0].strip()[:120] if clean else ""

        if not title:
            continue

        # Summary: prefer <p> child
        summary_node = next(
            (c for c in a.iter() if c.tag == "p" and c.text(strip=True)), None
        )
        summary = summary_node.text(strip=True)[:400] if summary_node else ""

        items.append(
            NewsItem(
                id=item_id,
                title=title,
                summary=summary,
                url=url,  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=NewsroomFetcher.source_key,
                category=categories,
                published_at=published_at,
                importance=3,
            )
        )

    # Return newest first, capped at 15
    items.sort(key=lambda x: x.published_at, reverse=True)
    return items[:15]


class NewsroomFetcher(Fetcher):
    source_key = "anthropic-newsroom"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
        return _parse_newsroom_html(resp.text)
