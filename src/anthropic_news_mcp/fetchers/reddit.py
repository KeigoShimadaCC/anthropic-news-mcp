"""Fetcher for hot posts from r/ClaudeAI and r/anthropic."""

import html as html_lib
import re
from datetime import UTC, datetime
from typing import Literal, cast

from ..http import get_client
from ..models import Category, DateConfidence, NewsItem, Source
from .base import Fetcher

_SUBREDDITS = ["ClaudeAI", "anthropic"]
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _decode(text: str) -> str:
    return html_lib.unescape(text)


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _importance(ups: int) -> Literal[1, 2]:
    return 2 if ups > 500 else 1


def _parse_subreddit(data: dict[str, object], subreddit: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    listing = cast(dict[str, object], data.get("data", {}))
    children = cast(list[dict[str, object]], listing.get("children", []))
    for child in children:
        post = cast(dict[str, object], child.get("data", {}))
        if post.get("stickied") or post.get("pinned"):
            continue

        post_id = str(post.get("id", ""))
        title = _decode(str(post.get("title") or "")).strip()
        if not title:
            continue

        try:
            ups = int(float(str(post.get("ups") or 0)))
        except (ValueError, TypeError):
            ups = 0
        try:
            num_comments = int(float(str(post.get("num_comments") or 0)))
        except (ValueError, TypeError):
            num_comments = 0
        selftext = _decode(_strip_html(str(post.get("selftext") or "")))

        summary = selftext[:300] if selftext.strip() else f"{ups} upvotes · {num_comments} comments"

        created_utc = float(str(post.get("created_utc") or 0))
        try:
            published_at = datetime.fromtimestamp(created_utc, tz=UTC)
        except (ValueError, OSError, OverflowError):
            published_at = None

        permalink = str(post.get("permalink") or "")
        url = f"https://reddit.com{permalink}"

        items.append(
            NewsItem(
                id=f"reddit-{post_id}",
                title=title,
                summary=summary,
                url=url,  # type: ignore[arg-type]
                source=Source.REDDIT,
                source_key=RedditFetcher.source_key,
                category=[Category.COMMUNITY],
                published_at=published_at,
                date_confidence=DateConfidence.EXACT if published_at else DateConfidence.UNKNOWN,
                importance=_importance(ups),
                author=f"u/{post.get('author', 'unknown')}",
            )
        )
    return items


class RedditFetcher(Fetcher):
    source_key = "reddit-claude"

    async def fetch(self) -> list[NewsItem]:
        # Reddit blocks default User-Agents aggressively — use a named UA
        headers = {"User-Agent": "anthropic-news-mcp/1.0"}
        all_items: list[NewsItem] = []

        async with get_client(headers=headers) as client:
            for sub in _SUBREDDITS:
                resp = await client.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=10")
                if resp.status_code in (403, 429):
                    continue
                resp.raise_for_status()
                all_items.extend(_parse_subreddit(resp.json(), sub))

        all_items.sort(key=lambda x: x.sort_at or x.discovered_at, reverse=True)
        return all_items
