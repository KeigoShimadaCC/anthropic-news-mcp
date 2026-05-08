from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import Category, EvidenceTier, SourceType

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
    source_type: SourceType = SourceType.OFFICIAL
    evidence_tier: EvidenceTier = EvidenceTier.HIGH


def _build_registry() -> "list[SourceConfig]":
    from .fetchers.docs_api import ApiDocsFetcher
    from .fetchers.docs_claude_code import ClaudeCodeDocsFetcher
    from .fetchers.github_events import GitHubOrgEventsFetcher
    from .fetchers.github_issues import GitHubIssuesPullsFetcher
    from .fetchers.github_releases import GitHubReleasesFetcher
    from .fetchers.hackernews import HackerNewsFetcher
    from .fetchers.newsroom import NewsroomFetcher
    from .fetchers.official import (
        BusinessInfrastructureFetcher,
        ClaudeAppsDocsFetcher,
        EconomicIndexFetcher,
        EngineeringFetcher,
        ResearchFetcher,
        StatusFetcher,
        SupportReleaseNotesFetcher,
        SystemPromptsDocsFetcher,
        TrustPolicyFetcher,
    )
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
            source_type=SourceType.OFFICIAL,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-status",
            fetcher_cls=StatusFetcher,
            ttl_seconds=300,
            default_categories=[Category.OPS],
            description="Claude Status incidents and scheduled maintenance from status.claude.com",
        ),
        SourceConfig(
            key="anthropic-research",
            fetcher_cls=ResearchFetcher,
            ttl_seconds=3600,
            default_categories=[Category.RESEARCH],
            description="Anthropic research publications from anthropic.com/research",
        ),
        SourceConfig(
            key="anthropic-engineering",
            fetcher_cls=EngineeringFetcher,
            ttl_seconds=3600,
            default_categories=[Category.ENGINEERING],
            description="Anthropic engineering posts from anthropic.com/engineering",
        ),
        SourceConfig(
            key="anthropic-docs-claude-code",
            fetcher_cls=ClaudeCodeDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.CLAUDE_CODE],
            description="Claude Code release notes (CHANGELOG.md on GitHub)",
            source_type=SourceType.DOCS,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-docs-api",
            fetcher_cls=ApiDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.MODELS],
            description="Claude API release notes from platform.claude.com",
            source_type=SourceType.DOCS,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-docs-claude-apps",
            fetcher_cls=ClaudeAppsDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.MODELS],
            description="Claude Apps release notes from docs.claude.com",
            source_type=SourceType.DOCS,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-docs-system-prompts",
            fetcher_cls=SystemPromptsDocsFetcher,
            ttl_seconds=3600,
            default_categories=[Category.POLICY],
            description="System prompt release notes from docs.claude.com",
            source_type=SourceType.DOCS,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-support-release-notes",
            fetcher_cls=SupportReleaseNotesFetcher,
            ttl_seconds=3600,
            default_categories=[Category.MODELS],
            description="Claude Help Center release notes from support.claude.com",
            source_type=SourceType.DOCS,
            evidence_tier=EvidenceTier.HIGH,
        ),
        SourceConfig(
            key="anthropic-economic-index",
            fetcher_cls=EconomicIndexFetcher,
            ttl_seconds=7200,
            default_categories=[Category.ECONOMICS, Category.RESEARCH],
            description="Anthropic Economic Index and economic research updates",
        ),
        SourceConfig(
            key="anthropic-business-infrastructure",
            fetcher_cls=BusinessInfrastructureFetcher,
            ttl_seconds=3600,
            default_categories=[Category.BUSINESS],
            description="Official Anthropic business, compute, partnership, funding, and enterprise updates",
        ),
        SourceConfig(
            key="anthropic-trust-policy",
            fetcher_cls=TrustPolicyFetcher,
            ttl_seconds=3600,
            default_categories=[Category.POLICY],
            description="Official Anthropic trust, safety, policy, RSP, transparency, and safeguards updates",
        ),
        SourceConfig(
            key="anthropic-github-releases",
            fetcher_cls=GitHubReleasesFetcher,
            ttl_seconds=1800,
            default_categories=[Category.CLAUDE_CODE, Category.MODELS],
            description="GitHub releases from key anthropics/* repos",
            source_type=SourceType.GITHUB,
            evidence_tier=EvidenceTier.MEDIUM,
        ),
        SourceConfig(
            key="anthropic-github-events",
            fetcher_cls=GitHubOrgEventsFetcher,
            ttl_seconds=1800,
            default_categories=[Category.CLAUDE_CODE],
            description="New repos and releases from the anthropics GitHub org",
            source_type=SourceType.GITHUB,
            evidence_tier=EvidenceTier.MEDIUM,
        ),
        SourceConfig(
            key="anthropic-github-issues-prs",
            fetcher_cls=GitHubIssuesPullsFetcher,
            ttl_seconds=1800,
            default_categories=[Category.CLAUDE_CODE, Category.ENGINEERING],
            description="Recent issues and pull requests from selected Anthropic/MCP GitHub repos",
            source_type=SourceType.GITHUB,
            evidence_tier=EvidenceTier.MEDIUM,
        ),
        SourceConfig(
            key="hn-anthropic",
            fetcher_cls=HackerNewsFetcher,
            ttl_seconds=1800,
            default_categories=[Category.COMMUNITY],
            description="Hacker News stories about Anthropic/Claude (≥10 points)",
            source_type=SourceType.COMMUNITY,
            evidence_tier=EvidenceTier.LOW,
        ),
        SourceConfig(
            key="reddit-claude",
            fetcher_cls=RedditFetcher,
            ttl_seconds=3600,
            default_categories=[Category.COMMUNITY],
            description="Hot posts from r/ClaudeAI and r/anthropic",
            source_type=SourceType.COMMUNITY,
            evidence_tier=EvidenceTier.LOW,
        ),
    ]


SOURCE_REGISTRY: "list[SourceConfig]" = _build_registry()
