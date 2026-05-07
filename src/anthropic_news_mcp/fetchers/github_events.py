"""Fetcher for Anthropic GitHub org events (new repos, releases)."""

import os
from datetime import datetime, timezone

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_ORG_EVENTS_URL = "https://api.github.com/orgs/anthropics/events?per_page=50"


def _parse_events(data: list[dict[str, object]]) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()  # dedupe by (type, repo)

    for event in data:
        event_type = str(event.get("type", ""))
        repo_full = str(event.get("repo", {}).get("name", ""))  # type: ignore[union-attr]
        repo_name = repo_full.split("/")[-1]
        payload = event.get("payload", {})
        event_id = str(event.get("id", ""))

        created_raw = str(event.get("created_at", ""))
        try:
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.now(tz=timezone.utc)

        if event_type == "ReleaseEvent":
            action = str(payload.get("action", ""))  # type: ignore[union-attr]
            if action != "published":
                continue
            release = payload.get("release", {})  # type: ignore[union-attr]
            tag = str(release.get("tag_name", ""))  # type: ignore[union-attr]
            dedup_key = f"release-{repo_full}-{tag}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            items.append(
                NewsItem(
                    id=f"github-event-{event_id}",
                    title=f"{repo_name} {tag}",
                    summary=str(release.get("body") or "")[:400],  # type: ignore[union-attr]
                    url=f"https://github.com/{repo_full}/releases/tag/{tag}",  # type: ignore[arg-type]
                    source=Source.GITHUB,
                    source_key=GitHubOrgEventsFetcher.source_key,
                    category=[Category.CLAUDE_CODE],
                    published_at=created_at,
                    importance=2,
                )
            )

        elif event_type == "CreateEvent":
            ref_type = str(payload.get("ref_type", ""))  # type: ignore[union-attr]
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
                    summary=str(payload.get("description") or ""),  # type: ignore[union-attr]
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

        async with get_client(headers=headers) as client:
            resp = await client.get(_ORG_EVENTS_URL)
            resp.raise_for_status()

        return _parse_events(resp.json())
