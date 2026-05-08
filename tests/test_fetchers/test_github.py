import json
from pathlib import Path

import pytest

from anthropic_news_mcp.fetchers.github_events import _parse_events
from anthropic_news_mcp.fetchers.github_releases import GitHubReleasesFetcher, _parse_releases
from anthropic_news_mcp.models import Category, Source

RELEASES_FIXTURE = Path(__file__).parent.parent / "fixtures" / "github_releases.json"
EVENTS_FIXTURE = Path(__file__).parent.parent / "fixtures" / "github_events_synthetic.json"


class TestGitHubReleases:
    @pytest.fixture(scope="class")
    def items(self):
        data = json.loads(RELEASES_FIXTURE.read_bytes())
        return _parse_releases(data, "anthropics/claude-code")

    def test_returns_items(self, items):
        assert len(items) >= 1

    def test_skips_draft_releases(self):
        data = [
            {
                "id": 1,
                "tag_name": "v1.0",
                "name": "v1.0",
                "draft": True,
                "published_at": "2026-01-01T00:00:00Z",
                "body": "",
            }
        ]
        assert _parse_releases(data, "anthropics/test-repo") == []

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.GITHUB
            assert item.source_key == "anthropic-github-releases"

    def test_id_format(self, items):
        for item in items:
            assert item.id.startswith("github-release-")

    def test_title_contains_repo_and_tag(self, items):
        for item in items:
            assert "claude-code" in item.title.lower() or "v" in item.title

    def test_url_format(self, items):
        for item in items:
            assert "github.com" in str(item.url)
            assert "releases/tag" in str(item.url)

    def test_dates_parsed(self, items):
        for item in items:
            assert item.published_at.year >= 2024

    def test_no_duplicate_ids(self, items):
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_claude_code_category(self, items):
        for item in items:
            assert Category.CLAUDE_CODE in item.category

    def test_sdk_python_category(self):
        data = [
            {
                "id": 9999,
                "tag_name": "v0.50.0",
                "name": "v0.50.0",
                "draft": False,
                "published_at": "2026-01-01T00:00:00Z",
                "body": "new stuff",
            }
        ]
        items = _parse_releases(data, "anthropics/anthropic-sdk-python")
        assert Category.MODELS in items[0].category

    @pytest.mark.asyncio
    async def test_fetch_without_github_token_uses_unauthenticated_requests(self, monkeypatch):
        calls = []

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return []

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                calls.append(url)
                return FakeResponse()

        def fake_get_client(**kwargs):
            calls.append(kwargs)
            return FakeClient()

        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setattr(
            "anthropic_news_mcp.fetchers.github_releases.get_client",
            fake_get_client,
        )

        with pytest.warns(UserWarning, match="GITHUB_TOKEN not set"):
            items = await GitHubReleasesFetcher().fetch()

        assert items == []
        assert calls[0] == {"headers": {}}
        assert len(calls) == 5  # client kwargs + four repo requests


class TestGitHubOrgEvents:
    @pytest.fixture(scope="class")
    def items(self):
        data = json.loads(EVENTS_FIXTURE.read_bytes())
        return _parse_events(data)

    def test_returns_items(self, items):
        # Synthetic fixture has 1 ReleaseEvent + 1 new-repo CreateEvent
        assert len(items) == 2

    def test_release_event_parsed(self, items):
        releases = [i for i in items if "New repo" not in i.title]
        assert len(releases) == 1
        assert "claude-code" in releases[0].title.lower()

    def test_new_repo_event_parsed(self, items):
        new_repos = [i for i in items if "New repo" in i.title]
        assert len(new_repos) == 1
        assert "new-open-source-repo" in new_repos[0].title

    def test_branch_create_event_skipped(self, items):
        # another-repo branch create event should be skipped
        assert not any("another-repo" in i.title for i in items)

    def test_issues_event_skipped(self, items):
        assert not any("issue" in i.title.lower() for i in items)

    def test_dedup_by_repo_and_tag(self):
        data = [
            {
                "id": "a1",
                "type": "ReleaseEvent",
                "repo": {"name": "anthropics/claude-code"},
                "created_at": "2026-01-01T00:00:00Z",
                "payload": {
                    "action": "published",
                    "release": {"tag_name": "v1.0", "name": "v1.0", "body": ""},
                },
            },
            {
                "id": "a2",
                "type": "ReleaseEvent",
                "repo": {"name": "anthropics/claude-code"},
                "created_at": "2026-01-01T01:00:00Z",
                "payload": {
                    "action": "published",
                    "release": {"tag_name": "v1.0", "name": "v1.0", "body": ""},
                },
            },
        ]
        items = _parse_events(data)
        assert len(items) == 1

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.GITHUB
            assert item.source_key == "anthropic-github-events"

    def test_sorted_newest_first(self, items):
        for a, b in zip(items, items[1:], strict=False):
            assert a.published_at >= b.published_at
