"""Fetcher for recent GitHub issues and pull requests from selected repos."""

import os
from datetime import UTC, datetime
from urllib.parse import quote_plus

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_REPOS = [
    "anthropics/claude-code",
    "anthropics/anthropic-sdk-python",
    "anthropics/anthropic-sdk-typescript",
    "modelcontextprotocol/modelcontextprotocol",
]


def _parse_issue_search(data: dict[str, object]) -> list[NewsItem]:
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        return []
    items: list[NewsItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        number = raw.get("number")
        repo_url = str(raw.get("repository_url") or "")
        repo = repo_url.rsplit("/repos/", 1)[-1] if "/repos/" in repo_url else "github"
        title = str(raw.get("title") or "").strip()
        if not number or not title:
            continue
        labels = [
            str(label.get("name"))
            for label in raw.get("labels", [])
            if isinstance(label, dict) and label.get("name")
        ]
        is_pr = "pull_request" in raw
        created_raw = str(raw.get("updated_at") or raw.get("created_at") or "")
        try:
            published_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(tz=UTC)
        body = str(raw.get("body") or "")[:400]
        items.append(
            NewsItem(
                id=f"github-issue-{repo.replace('/', '-')}-{number}",
                title=f"{repo} {'PR' if is_pr else 'issue'} #{number}: {title}",
                summary=body,
                url=str(raw.get("html_url") or f"https://github.com/{repo}/issues/{number}"),  # type: ignore[arg-type]
                source=Source.GITHUB,
                source_key=GitHubIssuesPullsFetcher.source_key,
                category=[Category.CLAUDE_CODE, Category.ENGINEERING],
                published_at=published_at,
                importance=2 if is_pr else 1,
                tags=["github", "pull-request" if is_pr else "issue", *labels[:8]],
                author=str((raw.get("user") or {}).get("login", ""))
                if isinstance(raw.get("user"), dict)
                else None,
            )
        )
    items.sort(key=lambda item: item.published_at, reverse=True)
    return items


class GitHubIssuesPullsFetcher(Fetcher):
    source_key = "anthropic-github-issues-prs"

    async def fetch(self) -> list[NewsItem]:
        headers: dict[str, str] = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        repo_query = " ".join(f"repo:{repo}" for repo in _REPOS)
        query = quote_plus(f"{repo_query} updated:>=2025-01-01 sort:updated-desc")
        url = f"https://api.github.com/search/issues?q={query}&per_page=20"
        async with get_client(headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return _parse_issue_search(resp.json())
