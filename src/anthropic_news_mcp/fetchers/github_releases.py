"""Fetcher for GitHub releases from key anthropics/* repos."""

import os
import re
from datetime import UTC, datetime

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_REPOS = [
    "anthropics/claude-code",
    "anthropics/anthropic-sdk-python",
    "anthropics/anthropic-sdk-typescript",
    "modelcontextprotocol/modelcontextprotocol",
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _classify_repo(repo: str) -> list[Category]:
    name = repo.split("/")[-1].lower()
    if "claude-code" in name or "mcp" in name or "modelcontext" in name:
        return [Category.CLAUDE_CODE]
    if "sdk" in name:
        return [Category.MODELS, Category.CLAUDE_CODE]
    return [Category.CLAUDE_CODE]


def _parse_releases(data: list[dict[str, object]], repo: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    repo_name = repo.split("/")[-1]
    for release in data:
        if release.get("draft"):
            continue
        release_id = release["id"]
        tag = str(release.get("tag_name", ""))
        name = str(release.get("name") or tag)
        title = f"{repo_name} {tag}: {name}" if name != tag else f"{repo_name} {tag}"
        body = _strip_html(str(release.get("body") or ""))[:400]
        published_raw = release.get("published_at") or release.get("created_at", "")
        try:
            published_at = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(tz=UTC)

        items.append(
            NewsItem(
                id=f"github-release-{release_id}",
                title=title,
                summary=body,
                url=f"https://github.com/{repo}/releases/tag/{tag}",  # type: ignore[arg-type]
                source=Source.GITHUB,
                source_key=GitHubReleasesFetcher.source_key,
                category=_classify_repo(repo),
                published_at=published_at,
                importance=2,
            )
        )
    return items


class GitHubReleasesFetcher(Fetcher):
    source_key = "anthropic-github-releases"

    async def fetch(self) -> list[NewsItem]:
        headers: dict[str, str] = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            import warnings

            warnings.warn(
                "GITHUB_TOKEN not set — GitHub API rate limit is 60 req/hr. "
                "Set GITHUB_TOKEN for 5,000 req/hr.",
                stacklevel=2,
            )

        all_items: list[NewsItem] = []
        async with get_client(headers=headers) as client:
            for repo in _REPOS:
                resp = await client.get(f"https://api.github.com/repos/{repo}/releases?per_page=5")
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                all_items.extend(_parse_releases(resp.json(), repo))

        all_items.sort(key=lambda x: x.published_at, reverse=True)
        return all_items
