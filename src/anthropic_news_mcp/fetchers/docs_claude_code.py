"""Fetcher for Claude Code release notes (CHANGELOG.md on GitHub)."""

import re
from datetime import datetime, timezone

from ..http import get_client
from ..models import Category, NewsItem, Source
from .base import Fetcher

_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
_CANONICAL_URL = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md"

_VERSION_RE = re.compile(r"^## (.+)$")


def _parse_changelog_markdown(text: str, limit: int = 10) -> list[NewsItem]:
    """Parse a semver-based CHANGELOG.md into NewsItems.

    Each `## <version>` block becomes one item. No dates are present in this
    changelog so items are ordered by appearance and assigned a synthetic
    published_at offset (newest = now, older = now - n*minutes).
    """
    items: list[NewsItem] = []
    current_version: str | None = None
    current_bullets: list[str] = []
    now = datetime.now(tz=timezone.utc)

    def _flush(version: str, bullets: list[str], idx: int) -> None:
        if not version:
            return
        bullet_text = " · ".join(b.lstrip("- ").strip() for b in bullets if b.strip())[:400]
        # Synthetic time: subtract idx minutes so ordering is stable
        from datetime import timedelta

        published = now - timedelta(minutes=idx * 5)
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
                importance=2,
            )
        )

    idx = 0
    for line in text.splitlines():
        vm = _VERSION_RE.match(line)
        if vm:
            if current_version is not None:
                _flush(current_version, current_bullets, idx)
                idx += 1
                if len(items) >= limit:
                    break
            current_version = vm.group(1).strip()
            current_bullets = []
        elif line.startswith("- ") and current_version:
            current_bullets.append(line)

    if current_version and len(items) < limit:
        _flush(current_version, current_bullets, idx)

    return items[:limit]


class ClaudeCodeDocsFetcher(Fetcher):
    source_key = "anthropic-docs-claude-code"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
        return _parse_changelog_markdown(resp.text)
