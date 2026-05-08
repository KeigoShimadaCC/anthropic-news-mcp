"""Fetcher for Hacker News stories mentioning Anthropic/Claude."""

import re
from datetime import datetime, timezone

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query=anthropic+OR+%22claude+ai%22&tags=story&hitsPerPage=20"
)
_MIN_POINTS = 10


def _importance(points: int) -> int:
    if points > 500:
        return 3
    if points > 100:
        return 2
    return 1


def _parse_hn(data: dict[str, object]) -> list[NewsItem]:
    items: list[NewsItem] = []
    for hit in data.get("hits", []):  # type: ignore[union-attr]
        points = int(hit.get("points") or 0)  # type: ignore[arg-type]
        if points < _MIN_POINTS:
            continue

        obj_id = str(hit.get("objectID", ""))
        title = str(hit.get("title") or "").strip()
        if not title:
            continue

        url = str(hit.get("url") or f"https://news.ycombinator.com/item?id={obj_id}")
        num_comments = int(hit.get("num_comments") or 0)  # type: ignore[arg-type]
        story_text = str(hit.get("story_text") or "")

        if story_text:
            summary = re.sub(r"<[^>]+>", "", story_text)[:400]
        else:
            summary = f"{points} points · {num_comments} comments on Hacker News"

        created_raw = str(hit.get("created_at") or "")
        try:
            published_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(tz=timezone.utc)

        items.append(
            NewsItem(
                id=f"hn-{obj_id}",
                title=title,
                summary=summary,
                url=url,  # type: ignore[arg-type]
                source=Source.HACKERNEWS,
                source_key=HackerNewsFetcher.source_key,
                category=[Category.COMMUNITY],
                published_at=published_at,
                importance=_importance(points),
                author=str(hit.get("author") or ""),
            )
        )

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items


class HackerNewsFetcher(Fetcher):
    source_key = "hn-anthropic"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
        return _parse_hn(resp.json())
