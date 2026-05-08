from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthropic_news_mcp import cache as cache_mod
from anthropic_news_mcp.models import (
    Category,
    ContentDetail,
    EvidenceExcerpt,
    EvidenceTier,
    NewsItem,
    ResearchNote,
    ResearchReport,
    ResearchSession,
    Source,
    SourceStatus,
    SourceType,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    """Point the cache at a fresh temp DB for each test."""
    cache_mod.set_db_path(tmp_path / "test_cache.db")
    yield
    cache_mod.set_db_path(None)  # type: ignore[arg-type]


def _item(id: str, url: str = "https://anthropic.com/news/test") -> NewsItem:
    return NewsItem(
        id=id,
        title=f"Title {id}",
        summary=f"Summary for {id}",
        url=url,  # type: ignore[arg-type]
        source=Source.ANTHROPIC,
        source_key="anthropic-newsroom",
        category=[Category.MODELS],
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        importance=2,
    )


class TestDbPath:
    def test_env_cache_db_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        override = tmp_path / "custom" / "news.db"
        cache_mod._DB_PATH = None  # type: ignore[attr-defined]
        monkeypatch.setenv("ANTHROPIC_NEWS_MCP_CACHE_DB", str(override))
        assert cache_mod.get_db_path() == override
        assert override.parent.exists()

    def test_world_readable_dir_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_db_path() should warn when the cache directory is world-readable."""

        pub = tmp_path / "pub_cache"
        pub.mkdir(mode=0o777)
        cache_mod._DB_PATH = None  # type: ignore[attr-defined]
        monkeypatch.setenv("XDG_CACHE_HOME", str(pub))

        with pytest.warns(UserWarning, match="world-readable"):
            cache_mod.get_db_path()

    def test_stat_failure_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If stat() raises, get_db_path() should still return a path (non-fatal)."""
        cache_home = tmp_path / "stat_fail"
        expected_cache_dir = cache_home / "anthropic-news-mcp"
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
        cache_mod._DB_PATH = None  # type: ignore[attr-defined]

        original_stat = Path.stat

        def bad_stat(self: Path, **kwargs: object) -> object:
            if self == expected_cache_dir.resolve():
                raise OSError("simulated stat failure")
            return original_stat(self, **kwargs)

        monkeypatch.setattr(Path, "stat", bad_stat)
        result = cache_mod.get_db_path()
        assert result == expected_cache_dir / "cache.db"


class TestInit:
    def test_init_creates_tables(self, tmp_path: Path) -> None:
        cache_mod.init_db()
        import sqlite3

        db = sqlite3.connect(str(cache_mod.get_db_path()))
        tables = {
            r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        db.close()
        assert "source_snapshots" in tables
        assert "items" in tables
        assert "content_details" in tables
        assert "evidence_excerpts" in tables
        assert "research_sessions" in tables

    def test_idempotent_init(self) -> None:
        cache_mod.init_db()
        cache_mod.init_db()  # Should not raise


class TestFreshness:
    def test_not_fresh_when_empty(self) -> None:
        assert not cache_mod.is_fresh("anthropic-newsroom")

    def test_fresh_after_save(self) -> None:
        items = [_item("a1")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        assert cache_mod.is_fresh("anthropic-newsroom")

    def test_stale_after_ttl(self) -> None:
        items = [_item("a2")]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=0)
        # TTL=0 means expired immediately (expires_at == now, not > now)
        assert not cache_mod.is_fresh("anthropic-newsroom")

    def test_freshness_negative_ttl_treated_as_expired(self) -> None:
        items = [_item("a3")]
        # Simulate past expiry by saving with ttl=0
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=0)
        assert not cache_mod.is_fresh("anthropic-newsroom")


class TestSaveAndRetrieve:
    def test_round_trip(self) -> None:
        item = _item("b1", url="https://anthropic.com/news/unique")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        result = cache_mod.get_cached_items("anthropic-newsroom")
        assert len(result) == 1
        assert result[0].id == "b1"
        assert result[0].title == "Title b1"

    def test_empty_source_returns_empty_list(self) -> None:
        result = cache_mod.get_cached_items("nonexistent-source")
        assert result == []

    def test_snapshot_replaces_previous(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("c1")], ttl_seconds=3600)
        cache_mod.save_snapshot("anthropic-newsroom", [_item("c2"), _item("c3")], ttl_seconds=3600)
        result = cache_mod.get_cached_items("anthropic-newsroom")
        assert len(result) == 2
        assert {r.id for r in result} == {"c2", "c3"}

    def test_multiple_sources_isolated(self) -> None:
        cache_mod.save_snapshot("src-a", [_item("d1")], ttl_seconds=3600)
        cache_mod.save_snapshot("src-b", [_item("d2")], ttl_seconds=3600)
        assert len(cache_mod.get_cached_items("src-a")) == 1
        assert len(cache_mod.get_cached_items("src-b")) == 1

    def test_get_snapshot_returns_health(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("e1")], ttl_seconds=1800)
        health = cache_mod.get_snapshot("anthropic-newsroom")
        assert health is not None
        assert health.key == "anthropic-newsroom"
        assert health.status == SourceStatus.LIVE
        assert health.item_count == 1
        assert health.error is None

    def test_get_snapshot_none_when_missing(self) -> None:
        assert cache_mod.get_snapshot("missing") is None

    def test_save_with_error_status(self) -> None:
        cache_mod.save_snapshot(
            "anthropic-newsroom",
            [],
            ttl_seconds=0,
            status=SourceStatus.DOWN,
            error="connection refused",
        )
        health = cache_mod.get_snapshot("anthropic-newsroom")
        assert health is not None
        assert health.status == SourceStatus.DOWN
        assert health.error == "connection refused"


class TestSearch:
    def test_search_by_title(self) -> None:
        item = NewsItem(
            id="s1",
            title="Claude 3.5 Sonnet Released",
            summary="Major capability improvements",
            url="https://anthropic.com/news/sonnet",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            importance=3,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        results = cache_mod.search_items("sonnet")
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_search_case_insensitive(self) -> None:
        item = _item("s2")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        assert len(cache_mod.search_items("TITLE")) == 1
        assert len(cache_mod.search_items("title")) == 1

    def test_search_no_match_returns_empty(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("s3")], ttl_seconds=3600)
        results = cache_mod.search_items("xyzzy_nomatch")
        assert results == []

    def test_search_wildcard_percent_not_expanded(self) -> None:
        """'%' must be treated as a literal character, not a LIKE wildcard."""
        item_a = NewsItem(
            id="w1",
            title="Claude 3 update",
            summary="A real item",
            url="https://anthropic.com/news/w1",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            importance=1,
        )
        item_b = NewsItem(
            id="w2",
            title="Unrelated post",
            summary="No match here",
            url="https://anthropic.com/news/w2",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            importance=1,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item_a, item_b], ttl_seconds=3600)
        # Without fix: "%" → LIKE "%%" → matches every row (any sequence)
        # With fix:    "%" → LIKE "%\%%" ESCAPE '\' → literal "%" not in any payload → empty
        results = cache_mod.search_items("%")
        assert results == [], f"'%' should match nothing, got {len(results)} items"

    def test_search_wildcard_underscore_not_expanded(self) -> None:
        """'_' in a query must be treated as a literal character, not an any-char wildcard."""
        # item whose title contains "xspecial" — vulnerable LIKE "_special" would match
        # it (via x ↔ _), but the fixed literal search for "_special" should not.
        item_a = NewsItem(
            id="u1",
            title="xspecial announcement",
            summary="Contains xspecial",
            url="https://anthropic.com/news/u1",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            importance=1,
        )
        item_b = NewsItem(
            id="u2",
            title="Regular news",
            summary="Nothing here",
            url="https://anthropic.com/news/u2",  # type: ignore[arg-type]
            source=Source.ANTHROPIC,
            source_key="anthropic-newsroom",
            category=[Category.MODELS],
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            importance=1,
        )
        cache_mod.save_snapshot("anthropic-newsroom", [item_a, item_b], ttl_seconds=3600)
        # Without fix: "_special" → LIKE "%_special%" → matches "xspecial" → returns item_a
        # With fix:    "_special" → LIKE "%\_special%" ESCAPE '\' → literal "_special"
        #              not present in either payload → returns nothing
        results = cache_mod.search_items("_special")
        assert results == [], (
            f"'_special' wildcard should not match 'xspecial', got {len(results)} items"
        )

    def test_search_respects_limit(self) -> None:
        items = [
            NewsItem(
                id=f"lim{i}",
                title=f"Anthropic update {i}",
                summary="",
                url=f"https://anthropic.com/news/{i}",  # type: ignore[arg-type]
                source=Source.ANTHROPIC,
                source_key="anthropic-newsroom",
                category=[],
                published_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                importance=1,
            )
            for i in range(10)
        ]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        results = cache_mod.search_items("anthropic", limit=3)
        assert len(results) == 3


class TestSnapshotClearsStaleItems:
    def test_save_snapshot_clears_stale_items(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("x"), _item("y")], ttl_seconds=3600)
        cache_mod.save_snapshot("anthropic-newsroom", [_item("z")], ttl_seconds=3600)
        assert cache_mod.search_items("Title x") == []
        assert len(cache_mod.search_items("Title z")) == 1


class TestGetAllSnapshots:
    def test_returns_all_sources(self) -> None:
        cache_mod.save_snapshot("src-x", [_item("x1")], ttl_seconds=3600)
        cache_mod.save_snapshot("src-y", [_item("y1")], ttl_seconds=3600)
        healths = cache_mod.get_all_snapshots()
        keys = {h.key for h in healths}
        assert keys == {"src-x", "src-y"}

    def test_empty_when_no_data(self) -> None:
        assert cache_mod.get_all_snapshots() == []


class TestResearchPersistence:
    def test_content_detail_evidence_and_session_round_trip(self) -> None:
        item = _item("detail-1", "https://anthropic.com/news/detail")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        detail = ContentDetail(
            item_id=item.id,
            url=item.url,
            normalized_text="Claude released a detailed research update.",
            retrieved_at=datetime(2026, 1, 2, tzinfo=UTC),
            content_hash="abc123",
            content_type="text/html",
        )
        cache_mod.save_content_detail(detail)
        assert cache_mod.get_content_detail(item.id) == detail

        excerpt = EvidenceExcerpt(
            evidence_id="ev1",
            item_id=item.id,
            url=item.url,
            title=item.title,
            source_key=item.source_key,
            source_type=SourceType.OFFICIAL,
            evidence_tier=EvidenceTier.HIGH,
            text="Claude released a detailed research update.",
            start_char=0,
            end_char=41,
            retrieved_at=datetime(2026, 1, 2, tzinfo=UTC),
            content_hash="abc123",
        )
        cache_mod.save_evidence_excerpts([excerpt])
        assert cache_mod.get_evidence("ev1") == excerpt
        assert cache_mod.get_evidence_for_item(item.id) == [excerpt]

        session = ResearchSession(
            session_id="sess1",
            title="Research",
            topic="Claude",
            filters={},
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        cache_mod.save_research_session(session)
        note = ResearchNote(
            note_id="note1",
            session_id="sess1",
            text="Follow up",
            evidence_ids=["ev1"],
            follow_up=True,
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        report = ResearchReport(
            report_id="rep1",
            session_id="sess1",
            title="Report",
            markdown="# Report",
            evidence_ids=["ev1"],
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        cache_mod.save_research_note(note)
        cache_mod.save_research_report(report)
        assert cache_mod.get_research_session("sess1") == session
        assert cache_mod.get_research_notes("sess1") == [note]
        assert cache_mod.get_research_reports("sess1") == [report]


class TestGetItem:
    def test_returns_item_by_id(self) -> None:
        item = _item("gi-1")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        result = cache_mod.get_item("gi-1")
        assert result is not None
        assert result.id == "gi-1"

    def test_returns_none_for_unknown_id(self) -> None:
        assert cache_mod.get_item("nonexistent-id") is None


class TestGetAllItems:
    def test_returns_items_from_multiple_sources(self) -> None:
        cache_mod.save_snapshot("src-a", [_item("all-1")], ttl_seconds=3600)
        cache_mod.save_snapshot("src-b", [_item("all-2"), _item("all-3")], ttl_seconds=3600)
        result = cache_mod.get_all_items()
        ids = {item.id for item in result}
        assert {"all-1", "all-2", "all-3"}.issubset(ids)

    def test_empty_when_no_data(self) -> None:
        assert cache_mod.get_all_items() == []


class TestGetAllContentDetails:
    def test_returns_all_details(self) -> None:
        item1 = _item("cd-1")
        item2 = _item("cd-2")
        cache_mod.save_snapshot("anthropic-newsroom", [item1, item2], ttl_seconds=3600)
        for item in (item1, item2):
            cache_mod.save_content_detail(
                ContentDetail(
                    item_id=item.id,
                    url=item.url,
                    normalized_text=f"Text for {item.id}",
                    retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                    content_hash=f"hash-{item.id}",
                    content_type="text/html",
                )
            )
        result = cache_mod.get_all_content_details()
        assert {d.item_id for d in result} == {"cd-1", "cd-2"}

    def test_empty_when_no_details(self) -> None:
        assert cache_mod.get_all_content_details() == []


class TestSearchDetails:
    def test_finds_matching_text(self) -> None:
        item = _item("sd-1")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        cache_mod.save_content_detail(
            ContentDetail(
                item_id=item.id,
                url=item.url,
                normalized_text="Unique phrase about constitutional AI research.",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                content_hash="hash-sd-1",
                content_type="text/html",
            )
        )
        results = cache_mod.search_details("constitutional", limit=10)
        assert len(results) == 1
        assert results[0].item_id == "sd-1"

    def test_no_match_returns_empty(self) -> None:
        item = _item("sd-2")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        cache_mod.save_content_detail(
            ContentDetail(
                item_id=item.id,
                url=item.url,
                normalized_text="Some unrelated content.",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                content_hash="hash-sd-2",
                content_type="text/html",
            )
        )
        assert cache_mod.search_details("xyzzy_nomatch", limit=10) == []


class TestGetEvidenceMany:
    def test_returns_requested_excerpts(self) -> None:
        item = _item("em-1")
        cache_mod.save_snapshot("anthropic-newsroom", [item], ttl_seconds=3600)
        excerpts = [
            EvidenceExcerpt(
                evidence_id=f"ev-{i}",
                item_id=item.id,
                url=item.url,
                title=item.title,
                source_key=item.source_key,
                source_type=SourceType.OFFICIAL,
                evidence_tier=EvidenceTier.HIGH,
                text=f"Excerpt text {i}",
                start_char=i * 100,
                end_char=i * 100 + 50,
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                content_hash="hash-em",
            )
            for i in range(3)
        ]
        cache_mod.save_evidence_excerpts(excerpts)
        result = cache_mod.get_evidence_many(["ev-0", "ev-2"])
        ids = {e.evidence_id for e in result}
        assert ids == {"ev-0", "ev-2"}

    def test_skips_missing_ids(self) -> None:
        result = cache_mod.get_evidence_many(["does-not-exist"])
        assert result == []


class TestGetItemHistorySince:
    def test_returns_history_rows_for_seeded_items(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("hist-1")], ttl_seconds=3600)
        rows = cache_mod.get_item_history_since(None)
        assert len(rows) == 1
        assert rows[0]["item"].id == "hist-1"
        assert "first_seen_at" in rows[0]
        assert "last_changed_at" in rows[0]

    def test_since_filters_out_older_entries(self) -> None:
        cache_mod.save_snapshot("anthropic-newsroom", [_item("hist-2")], ttl_seconds=3600)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        rows = cache_mod.get_item_history_since(future)
        assert rows == []

    def test_respects_limit(self) -> None:
        items = [_item(f"hist-lim-{i}") for i in range(5)]
        cache_mod.save_snapshot("anthropic-newsroom", items, ttl_seconds=3600)
        rows = cache_mod.get_item_history_since(None, limit=2)
        assert len(rows) == 2
