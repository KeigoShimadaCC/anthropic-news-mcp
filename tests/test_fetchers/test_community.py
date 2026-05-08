import json
from datetime import UTC
from pathlib import Path

import pytest

from anthropic_news_mcp.fetchers.hackernews import _importance, _parse_hn
from anthropic_news_mcp.fetchers.reddit import _parse_subreddit
from anthropic_news_mcp.models import Category, Source

HN_FIXTURE = Path(__file__).parent.parent / "fixtures" / "hackernews.json"
REDDIT_CC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "reddit_claudeai.json"
REDDIT_AN_FIXTURE = Path(__file__).parent.parent / "fixtures" / "reddit_anthropic.json"


class TestHackerNews:
    @pytest.fixture(scope="class")
    def items(self):
        data = json.loads(HN_FIXTURE.read_bytes())
        return _parse_hn(data)

    def test_filters_low_point_stories(self):
        data = {
            "hits": [
                {
                    "objectID": "1",
                    "title": "Cool story",
                    "points": 5,
                    "url": "https://example.com",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        }
        assert _parse_hn(data) == []

    def test_includes_stories_above_threshold(self):
        data = {
            "hits": [
                {
                    "objectID": "2",
                    "title": "Anthropic news",
                    "points": 10,
                    "url": "https://example.com",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        }
        assert len(_parse_hn(data)) == 1

    def test_importance_scale(self):
        assert _importance(9) == 1
        assert _importance(100) == 1
        assert _importance(101) == 2
        assert _importance(500) == 2
        assert _importance(501) == 3

    def test_uses_hn_url_when_no_url(self):
        data = {
            "hits": [
                {
                    "objectID": "99",
                    "title": "Ask HN: Something",
                    "points": 50,
                    "url": None,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        }
        items = _parse_hn(data)
        assert "news.ycombinator.com/item?id=99" in str(items[0].url)

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.HACKERNEWS
            assert item.source_key == "hn-anthropic"

    def test_category_community(self, items):
        for item in items:
            assert Category.COMMUNITY in item.category

    def test_no_duplicate_ids(self, items):
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_ids_prefix(self, items):
        for item in items:
            assert item.id.startswith("hn-")

    def test_sorted_newest_first(self, items):
        for a, b in zip(items, items[1:], strict=False):
            assert a.published_at >= b.published_at


class TestReddit:
    @pytest.fixture(scope="class")
    def items(self):
        cc = json.loads(REDDIT_CC_FIXTURE.read_bytes())
        an = json.loads(REDDIT_AN_FIXTURE.read_bytes())
        return _parse_subreddit(cc, "ClaudeAI") + _parse_subreddit(an, "anthropic")

    def test_skips_stickied_posts(self):
        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "title": "Stickied post",
                            "stickied": True,
                            "ups": 100,
                            "num_comments": 5,
                            "selftext": "",
                            "created_utc": 1735689600.0,
                            "permalink": "/r/ClaudeAI/comments/abc/stickied/",
                            "author": "mod",
                        }
                    }
                ]
            }
        }
        assert _parse_subreddit(data, "ClaudeAI") == []

    def test_source_fields(self, items):
        for item in items:
            assert item.source == Source.REDDIT
            assert item.source_key == "reddit-claude"

    def test_category_community(self, items):
        for item in items:
            assert Category.COMMUNITY in item.category

    def test_ids_prefix(self, items):
        for item in items:
            assert item.id.startswith("reddit-")

    def test_no_duplicate_ids_within_subreddit(self):
        cc = json.loads(REDDIT_CC_FIXTURE.read_bytes())
        items = _parse_subreddit(cc, "ClaudeAI")
        ids = [i.id for i in items]
        assert len(ids) == len(set(ids))

    def test_url_contains_reddit(self, items):
        for item in items:
            assert "reddit.com" in str(item.url)

    def test_author_prefix(self, items):
        for item in items:
            if item.author:
                assert item.author.startswith("u/")

    def test_invalid_timestamp_falls_back_to_now(self):
        """Malformed created_utc must not crash the parser."""
        from datetime import datetime

        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "ts1",
                            "title": "Overflow timestamp",
                            "stickied": False,
                            "pinned": False,
                            "ups": 50,
                            "num_comments": 1,
                            "selftext": "",
                            "created_utc": float("inf"),
                            "permalink": "/r/ClaudeAI/comments/ts1/test/",
                            "author": "user",
                        }
                    }
                ]
            }
        }
        before = datetime.now(tz=UTC)
        items = _parse_subreddit(data, "ClaudeAI")
        after = datetime.now(tz=UTC)
        assert len(items) == 1
        assert before <= items[0].published_at <= after

    def test_non_numeric_ups_falls_back_to_zero(self):
        """Non-numeric ups/num_comments must not crash the parser."""
        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "num1",
                            "title": "Post with bad numeric fields",
                            "stickied": False,
                            "pinned": False,
                            "ups": "many",
                            "num_comments": "lots",
                            "selftext": "",
                            "created_utc": 1735689600.0,
                            "permalink": "/r/ClaudeAI/comments/num1/test/",
                            "author": "user",
                        }
                    }
                ]
            }
        }
        items = _parse_subreddit(data, "ClaudeAI")
        assert len(items) == 1
        assert items[0].importance == 1  # ups fell back to 0

    def test_html_entities_decoded(self):
        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "xyz",
                            "title": "Claude&#39;s new feature &amp; improvements",
                            "stickied": False,
                            "pinned": False,
                            "ups": 50,
                            "num_comments": 10,
                            "selftext": "",
                            "created_utc": 1735689600.0,
                            "permalink": "/r/ClaudeAI/comments/xyz/test/",
                            "author": "testuser",
                        }
                    }
                ]
            }
        }
        items = _parse_subreddit(data, "ClaudeAI")
        assert "'" in items[0].title or "&#39;" not in items[0].title
        assert "&amp;" not in items[0].title
