"""Deterministic cache seeding shared by eval harnesses."""

from datetime import UTC, datetime
from pathlib import Path


def seed_eval_cache(db_path: Path | None = None) -> None:
    """Seed stable offline snapshots for evals and tests.

    When ``db_path`` is provided, the project cache is redirected there first.
    """
    import sys

    root = Path(__file__).parent.parent
    sys.path.insert(0, str(root / "src"))

    from anthropic_news_mcp import cache
    from anthropic_news_mcp.config import SOURCE_REGISTRY
    from anthropic_news_mcp.models import Category, NewsItem, Source

    if db_path is not None:
        cache.set_db_path(db_path)

    now = datetime(2026, 5, 8, tzinfo=UTC)
    seed_items = {
        "anthropic-newsroom": [
            (
                "seed-news-1",
                "Claude model update",
                [Category.MODELS],
                "Latest Claude announcement.",
            ),
            (
                "seed-news-2",
                "Responsible Scaling Policy update",
                [Category.POLICY],
                "RSP safety update.",
            ),
        ],
        "anthropic-status": [
            (
                "seed-status-1",
                "Claude Status: All Systems Operational",
                [Category.OPS],
                "No active incidents.",
            ),
        ],
        "anthropic-research": [
            (
                "seed-research-1",
                "Research paper on model behavior",
                [Category.RESEARCH],
                "Anthropic research publication.",
            ),
        ],
        "anthropic-engineering": [
            (
                "seed-eng-1",
                "Building effective agents",
                [Category.ENGINEERING],
                "Engineering post about agents.",
            ),
        ],
        "anthropic-docs-claude-code": [
            (
                "seed-code-1",
                "Claude Code changelog",
                [Category.CLAUDE_CODE],
                "Claude Code release shipped this week.",
            ),
        ],
        "anthropic-docs-api": [
            (
                "seed-api-1",
                "API Release Notes: Sonnet 4.5",
                [Category.MODELS],
                "API model release notes.",
            ),
        ],
        "anthropic-docs-claude-apps": [
            (
                "seed-apps-1",
                "Claude Apps Release Notes",
                [Category.MODELS],
                "Desktop and mobile app updates.",
            ),
        ],
        "anthropic-docs-system-prompts": [
            (
                "seed-prompts-1",
                "System Prompt Release Notes",
                [Category.POLICY],
                "System prompt transparency changes.",
            ),
        ],
        "anthropic-support-release-notes": [
            (
                "seed-support-1",
                "Claude Help Center Release Notes",
                [Category.MODELS],
                "Claude app release notes.",
            ),
        ],
        "anthropic-economic-index": [
            (
                "seed-econ-1",
                "Anthropic Economic Index",
                [Category.ECONOMICS, Category.RESEARCH],
                "Economic research on AI at work.",
            ),
        ],
        "anthropic-business-infrastructure": [
            (
                "seed-biz-1",
                "Compute partnership expansion",
                [Category.BUSINESS],
                "Business infrastructure and enterprise demand.",
            ),
        ],
        "anthropic-trust-policy": [
            (
                "seed-trust-1",
                "Trust and safety transparency update",
                [Category.POLICY],
                "Safeguards, red-team, and policy update.",
            ),
        ],
        "anthropic-github-releases": [
            ("seed-gh-1", "Python SDK release", [Category.MODELS], "Anthropic Python SDK release."),
        ],
        "anthropic-github-events": [
            (
                "seed-ghe-1",
                "New anthropics repository",
                [Category.CLAUDE_CODE],
                "GitHub org event.",
            ),
        ],
        "anthropic-github-issues-prs": [
            (
                "seed-gh-issues-1",
                "Claude Code issue triage",
                [Category.CLAUDE_CODE, Category.ENGINEERING],
                "Recent issue and pull request activity.",
            ),
        ],
        "hn-anthropic": [
            (
                "seed-hn-1",
                "HN discussion about Anthropic",
                [Category.COMMUNITY],
                "Hacker News story with points.",
            ),
        ],
        "reddit-claude": [
            (
                "seed-reddit-1",
                "r/ClaudeAI community post",
                [Category.COMMUNITY],
                "Reddit community discussion.",
            ),
        ],
    }

    for config in SOURCE_REGISTRY:
        raw_items = seed_items.get(config.key, [])
        items = [
            NewsItem(
                id=item_id,
                title=title,
                summary=summary,
                url=f"https://anthropic.com/news/{item_id}",  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key=config.key,
                category=categories,
                published_at=now,
                importance=2,
            )
            for item_id, title, categories, summary in raw_items
        ]
        cache.save_snapshot(config.key, items, ttl_seconds=24 * 3600)
