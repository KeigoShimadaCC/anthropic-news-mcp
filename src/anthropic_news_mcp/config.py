from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import Category

if TYPE_CHECKING:
    from .fetchers.base import Fetcher


@dataclass(frozen=True)
class SourceConfig:
    key: str
    fetcher_cls: "type[Fetcher]"
    ttl_seconds: int
    default_categories: list[Category] = field(default_factory=list)
    enabled: bool = True
    description: str = ""


def _build_registry() -> "list[SourceConfig]":
    from .fetchers.docs_api import ApiDocsFetcher
    from .fetchers.docs_claude_code import ClaudeCodeDocsFetcher
    from .fetchers.github_events import GitHubOrgEventsFetcher
    from .fetchers.github_releases import GitHubReleasesFetcher
    from .fetchers.hackernews import HackerNewsFetcher
    from .fetchers.newsroom import NewsroomFetcher
    from .fetchers.reddit import RedditFetcher

    return [
        SourceConfig(
            key="anthropic-newsroom",
            fetcher_cls=NewsroomFetcher,
            ttl_seconds=1800,
            default_categories=[
                Category.MODELS,
                Category.RESEARCH,
                Category.POLICY,
                Category.BUSINESS,
            ],
            description="Anthropic's official news page (anthropic.com/news)",
        ),
        SourceConfig(
            key="anthropic-docs-claude-code",
            fetcher_cls=ClaudeCodeDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.CLAUDE_CODE],
            description="Claude Code release notes (CHANGELOG.md on GitHub)",
        ),
        SourceConfig(
            key="anthropic-docs-api",
            fetcher_cls=ApiDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.MODELS],
            description="Claude API release notes from platform.claude.com",
        ),
        SourceConfig(
            key="anthropic-github-releases",
            fetcher_cls=GitHubReleasesFetcher,
            ttl_seconds=1800,
            default_categories=[Category.CLAUDE_CODE, Category.MODELS],
            description="GitHub releases from key anthropics/* repos",
        ),
        SourceConfig(
            key="anthropic-github-events",
            fetcher_cls=GitHubOrgEventsFetcher,
            ttl_seconds=1800,
            default_categories=[Category.CLAUDE_CODE],
            description="New repos and releases from the anthropics GitHub org",
        ),
        SourceConfig(
            key="hn-anthropic",
            fetcher_cls=HackerNewsFetcher,
            ttl_seconds=1800,
            default_categories=[Category.COMMUNITY],
            description="Hacker News stories about Anthropic/Claude (≥10 points)",
        ),
        SourceConfig(
            key="reddit-claude",
            fetcher_cls=RedditFetcher,
            ttl_seconds=3600,
            default_categories=[Category.COMMUNITY],
            description="Hot posts from r/ClaudeAI and r/anthropic",
        ),
    ]


SOURCE_REGISTRY: "list[SourceConfig]" = _build_registry()
