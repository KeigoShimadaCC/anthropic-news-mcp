"""Fetcher for Anthropic GitHub org events (new repos, releases)."""

import logging
import os
from datetime import UTC, datetime
from typing import cast

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_log = logging.getLogger(__name__)

_ORG_EVENTS_URL = "https://api.github.com/orgs/anthropics/events?per_page=50"


def _parse_events(data: list[dict[str, object]]) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()  # dedupe by (type, repo)

    for event in data:
        event_type = str(event.get("type", ""))
        repo = cast(dict[str, object], event.get("repo", {}))
        repo_full = str(repo.get("name", ""))
        repo_name = repo_full.split("/")[-1]
        payload = cast(dict[str, object], event.get("payload", {}))
        event_id = str(event.get("id", ""))

        created_raw = str(event.get("created_at", ""))
        try:
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.now(tz=UTC)

        if event_type == "ReleaseEvent":
            action = str(payload.get("action", ""))
            if action != "published":
                continue
            release = cast(dict[str, object], payload.get("release", {}))
            tag = str(release.get("tag_name", ""))
            dedup_key = f"release-{repo_full}-{tag}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            items.append(
                NewsItem(
                    id=f"github-event-{event_id}",
                    title=f"{repo_name} {tag}",
                    summary=str(release.get("body") or "")[:400],
                    url=f"https://github.com/{repo_full}/releases/tag/{tag}",  # type: ignore[arg-type]
                    source=Source.GITHUB,
                    source_key=GitHubOrgEventsFetcher.source_key,
                    category=[Category.CLAUDE_CODE],
                    published_at=created_at,
                    importance=2,
                )
            )

        elif event_type == "CreateEvent":
            ref_type = str(payload.get("ref_type", ""))
            if ref_type != "repository":
                continue
            dedup_key = f"create-{repo_full}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            items.append(
                NewsItem(
                    id=f"github-event-{event_id}",
                    title=f"New repo created: {repo_name}",
                    summary=str(payload.get("description") or ""),
                    url=f"https://github.com/{repo_full}",  # type: ignore[arg-type]
                    source=Source.GITHUB,
                    source_key=GitHubOrgEventsFetcher.source_key,
                    category=[Category.CLAUDE_CODE],
                    published_at=created_at,
                    importance=2,
                )
            )

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items


class GitHubOrgEventsFetcher(Fetcher):
    source_key = "anthropic-github-events"

    async def fetch(self) -> list[NewsItem]:
        headers: dict[str, str] = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            _log.warning(
                "GITHUB_TOKEN not set; GitHub Events API rate-limited to 60 req/hr unauthenticated"
            )

        async with get_client(headers=headers) as client:
            resp = await client.get(_ORG_EVENTS_URL)
            resp.raise_for_status()

        return _parse_events(resp.json())
