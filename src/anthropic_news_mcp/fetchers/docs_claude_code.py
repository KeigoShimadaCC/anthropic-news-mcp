"""Fetcher for Claude Code release notes (CHANGELOG.md on GitHub)."""

import re

from ..http import get_client
from ..models import Category, DateConfidence, NewsItem, Source
from .base import Fetcher

_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
_CANONICAL_URL = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md"
_RELEASES_URL = "https://api.github.com/repos/anthropics/claude-code/releases?per_page=100"

_VERSION_RE = re.compile(r"^## (.+)$")


def _version_keys(version: str) -> set[str]:
    clean = version.strip()
    return {clean, clean.lstrip("v"), f"v{clean.lstrip('v')}"}


def _parse_changelog_markdown(
    text: str, release_dates: dict[str, str] | None = None, limit: int = 10
) -> list[NewsItem]:
    """Parse a semver-based CHANGELOG.md into NewsItems.

    Each `## <version>` block becomes one item. The changelog has no inline
    dates, so exact published dates are only used when a GitHub release tag
    matches the changelog version.
    """
    items: list[NewsItem] = []
    current_version: str | None = None
    current_bullets: list[str] = []
    release_dates = release_dates or {}

    def _flush(version: str, bullets: list[str]) -> None:
        if not version:
            return
        bullet_text = " · ".join(b.lstrip("- ").strip() for b in bullets if b.strip())[:400]
        published = None
        for key in _version_keys(version):
            raw = release_dates.get(key)
            if not raw:
                continue
            from datetime import datetime

            try:
                published = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                break
            except ValueError:
                continue
        items.append(
            NewsItem(
                id=f"docs-cc-{version.replace('.', '-')}",
                title=f"Claude Code {version}",
                summary=bullet_text,
                url=_CANONICAL_URL,  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=ClaudeCodeDocsFetcher.source_key,
                category=[Category.CLAUDE_CODE],
                published_at=published,
                date_confidence=DateConfidence.EXACT if published else DateConfidence.UNKNOWN,
                importance=2,
            )
        )

    for line in text.splitlines():
        vm = _VERSION_RE.match(line)
        if vm:
            if current_version is not None:
                _flush(current_version, current_bullets)
                if len(items) >= limit:
                    break
            current_version = vm.group(1).strip()
            current_bullets = []
        elif line.startswith("- ") and current_version:
            current_bullets.append(line)

    if current_version and len(items) < limit:
        _flush(current_version, current_bullets)

    return items[:limit]


class ClaudeCodeDocsFetcher(Fetcher):
    source_key = "anthropic-docs-claude-code"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
            releases_resp = await client.get(_RELEASES_URL)
            release_dates: dict[str, str] = {}
            if releases_resp.status_code < 400:
                for release in releases_resp.json():
                    if isinstance(release, dict):
                        tag = str(release.get("tag_name") or "")
                        published = str(release.get("published_at") or "")
                        if tag and published:
                            release_dates[tag] = published
        return _parse_changelog_markdown(resp.text, release_dates=release_dates)
