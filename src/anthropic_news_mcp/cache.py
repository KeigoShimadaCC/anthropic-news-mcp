import json
import os
import re
import sqlite3
import time
import warnings
from collections.abc import Generator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    ContentDetail,
    EvidenceExcerpt,
    EvidenceTier,
    NewsItem,
    ResearchNote,
    ResearchReport,
    ResearchSession,
    SourceHealth,
    SourceStatus,
    SourceType,
)

CACHE_SCHEMA_VERSION = 3

_DB_PATH: Path | None = None
_db_initialized: bool = False


def get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is not None:
        return _DB_PATH
    override = os.environ.get("ANTHROPIC_NEWS_MCP_CACHE_DB")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_absolute():
            raise RuntimeError(
                f"ANTHROPIC_NEWS_MCP_CACHE_DB must resolve to an absolute path, got: {override!r}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    path = Path(cache_home) / "anthropic-news-mcp" / "cache.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.parent.resolve()
    try:
        if resolved.stat().st_mode & 0o007:
            warnings.warn(
                f"Cache directory {resolved} is world-readable; "
                "set XDG_CACHE_HOME to a private directory to restrict access.",
                stacklevel=2,
            )
    except OSError:
        pass
    return path


def set_db_path(path: Path) -> None:
    """Override the default db path — used in tests."""
    global _DB_PATH, _db_initialized
    _DB_PATH = path
    _db_initialized = False


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    db = sqlite3.connect(str(get_db_path()))
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    global _db_initialized
    if _db_initialized:
        return
    _db_initialized = True
    with _conn() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        row = db.execute("SELECT version FROM schema_version").fetchone()
        if row and row["version"] > CACHE_SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported cache schema version: {row['version']}")

        db.execute("""
            CREATE TABLE IF NOT EXISTS source_snapshots (
                source_key   TEXT PRIMARY KEY,
                fetched_at   INTEGER NOT NULL,
                expires_at   INTEGER NOT NULL,
                status       TEXT NOT NULL,
                item_count   INTEGER NOT NULL,
                error        TEXT,
                items_json   TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id            TEXT PRIMARY KEY,
                source_key    TEXT NOT NULL,
                url           TEXT NOT NULL,
                published_at  INTEGER NOT NULL,
                payload_json  TEXT NOT NULL
            )
        """)
        with suppress(sqlite3.OperationalError):
            db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                    id UNINDEXED,
                    title,
                    summary,
                    tags,
                    source_key,
                    source_type,
                    evidence_tier,
                    tokenize='unicode61'
                )
            """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS content_details (
                item_id         TEXT PRIMARY KEY,
                url             TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                retrieved_at    INTEGER NOT NULL,
                content_hash    TEXT NOT NULL,
                content_type    TEXT NOT NULL,
                truncated       INTEGER NOT NULL,
                warnings_json   TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS evidence_excerpts (
                evidence_id    TEXT PRIMARY KEY,
                item_id        TEXT NOT NULL,
                url            TEXT NOT NULL,
                title          TEXT NOT NULL,
                source_key     TEXT NOT NULL,
                source_type    TEXT NOT NULL,
                evidence_tier  TEXT NOT NULL,
                text           TEXT NOT NULL,
                start_char     INTEGER NOT NULL,
                end_char       INTEGER NOT NULL,
                retrieved_at   INTEGER NOT NULL,
                content_hash   TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS item_history (
                id              TEXT PRIMARY KEY,
                item_id         TEXT NOT NULL,
                first_seen_at   INTEGER NOT NULL,
                last_seen_at    INTEGER NOT NULL,
                last_changed_at INTEGER NOT NULL,
                content_hash    TEXT,
                payload_json    TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS research_sessions (
                session_id   TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                topic        TEXT,
                filters_json TEXT NOT NULL,
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS research_notes (
                note_id           TEXT PRIMARY KEY,
                session_id        TEXT NOT NULL,
                text              TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                follow_up         INTEGER NOT NULL,
                created_at        INTEGER NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS research_reports (
                report_id         TEXT PRIMARY KEY,
                session_id        TEXT NOT NULL,
                title             TEXT NOT NULL,
                markdown          TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                created_at        INTEGER NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_key)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_details_hash ON content_details(content_hash)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_item ON evidence_excerpts(item_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_item ON item_history(item_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_notes_session ON research_notes(session_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_reports_session ON research_reports(session_id)")
        db.execute("DELETE FROM schema_version")
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (CACHE_SCHEMA_VERSION,))
        db.commit()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _item_sort_ms(item: NewsItem) -> int:
    return _dt_to_ms(item.sort_at or item.published_at or item.discovered_at)


def _source_metadata(source_key: str) -> tuple[SourceType, EvidenceTier, bool]:
    from .config import SOURCE_REGISTRY

    config = next((source for source in SOURCE_REGISTRY if source.key == source_key), None)
    if config is None:
        return SourceType.OFFICIAL, EvidenceTier.HIGH, True
    return (
        config.source_type,
        config.evidence_tier,
        config.source_type in {SourceType.OFFICIAL, SourceType.DOCS},
    )


def _enrich_item(item: NewsItem) -> NewsItem:
    source_type, evidence_tier, is_official = _source_metadata(item.source_key)
    return item.model_copy(
        update={
            "source_type": source_type,
            "evidence_tier": evidence_tier,
            "is_official": is_official,
        }
    )


def get_snapshot(source_key: str) -> SourceHealth | None:
    """Return the cached health record for a source, or None if not cached."""
    init_db()
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM source_snapshots WHERE source_key = ?", (source_key,)
        ).fetchone()
    if row is None:
        return None
    return SourceHealth(
        key=row["source_key"],
        status=SourceStatus(row["status"]),
        fetched_at=_ms_to_dt(row["fetched_at"]),
        expires_at=_ms_to_dt(row["expires_at"]),
        item_count=row["item_count"],
        error=row["error"],
    )


def is_fresh(source_key: str) -> bool:
    """Return True if the snapshot exists and has not yet expired."""
    init_db()
    now = _now_ms()
    with _conn() as db:
        row = db.execute(
            "SELECT expires_at FROM source_snapshots WHERE source_key = ?",
            (source_key,),
        ).fetchone()
    return row is not None and row["expires_at"] > now


def get_cached_items(source_key: str) -> list[NewsItem]:
    """Return items from the cache for a source, regardless of freshness."""
    init_db()
    with _conn() as db:
        row = db.execute(
            "SELECT items_json FROM source_snapshots WHERE source_key = ?",
            (source_key,),
        ).fetchone()
    if row is None:
        return []
    raw: list[dict[str, object]] = json.loads(row["items_json"])
    return [_enrich_item(NewsItem.model_validate(item)) for item in raw]


def save_snapshot(
    source_key: str,
    items: list[NewsItem],
    ttl_seconds: int,
    status: SourceStatus = SourceStatus.LIVE,
    error: str | None = None,
) -> None:
    """Persist a fetch result to cache."""
    init_db()
    items = [_enrich_item(item) for item in items]
    now = _now_ms()
    expires = now + ttl_seconds * 1000
    items_json = json.dumps([item.model_dump(mode="json") for item in items])

    with _conn() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO source_snapshots
                (source_key, fetched_at, expires_at, status, item_count, error, items_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_key, now, expires, status.value, len(items), error, items_json),
        )
        # Sync items table: remove stale rows, then batch-insert current set
        current_ids = {item.id for item in items}
        old_rows = db.execute(
            "SELECT id, payload_json FROM items WHERE source_key = ?", (source_key,)
        ).fetchall()
        now_ms = _now_ms()
        for old_row in old_rows:
            if old_row["id"] in current_ids:
                continue
            old_item = NewsItem.model_validate_json(old_row["payload_json"])
            existing = db.execute(
                "SELECT first_seen_at, content_hash FROM item_history WHERE item_id = ?",
                (old_item.id,),
            ).fetchone()
            db.execute(
                """
                INSERT OR REPLACE INTO item_history
                    (id, item_id, first_seen_at, last_seen_at, last_changed_at, content_hash, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    old_item.id,
                    old_item.id,
                    existing["first_seen_at"] if existing else now_ms,
                    now_ms,
                    now_ms,
                    existing["content_hash"] if existing else None,
                    old_item.model_dump_json(),
                ),
            )
        db.execute("DELETE FROM items WHERE source_key = ?", (source_key,))
        rows = [
            (
                item.id,
                item.source_key,
                str(item.url),
                _item_sort_ms(item),
                item.model_dump_json(),
            )
            for item in items
        ]
        db.executemany(
            "INSERT OR REPLACE INTO items (id, source_key, url, published_at, payload_json) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        _sync_items_fts(db, source_key, items)
        # Batch-fetch existing history rows and content hashes for all items at once.
        item_ids = [item.id for item in items]
        placeholders = ",".join("?" * len(item_ids))
        existing_history: dict[str, sqlite3.Row] = {}
        if item_ids:
            for row in db.execute(
                f"SELECT item_id, first_seen_at, last_changed_at, content_hash FROM item_history WHERE item_id IN ({placeholders})",
                item_ids,
            ).fetchall():
                existing_history[row["item_id"]] = row
            content_hashes: dict[str, str | None] = {}
            for row in db.execute(
                f"SELECT item_id, content_hash FROM content_details WHERE item_id IN ({placeholders})",
                item_ids,
            ).fetchall():
                content_hashes[row["item_id"]] = row["content_hash"]
        history_rows = []
        for item in items:
            existing = existing_history.get(item.id)
            detail_hash = content_hashes.get(item.id)
            first_seen_at = existing["first_seen_at"] if existing else now_ms
            if existing is None or existing["content_hash"] != detail_hash:
                last_changed_at = now_ms
            else:
                last_changed_at = existing["last_changed_at"]
            history_rows.append(
                (
                    item.id,
                    item.id,
                    first_seen_at,
                    now_ms,
                    last_changed_at,
                    detail_hash,
                    item.model_dump_json(),
                )
            )
        db.executemany(
            """
            INSERT OR REPLACE INTO item_history
                (id, item_id, first_seen_at, last_seen_at, last_changed_at, content_hash, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            history_rows,
        )
        db.commit()


def _detail_hash_for_db(db: sqlite3.Connection, item_id: str) -> str | None:
    row = db.execute(
        "SELECT content_hash FROM content_details WHERE item_id = ?", (item_id,)
    ).fetchone()
    return row["content_hash"] if row else None


def get_item(item_id: str) -> NewsItem | None:
    init_db()
    with _conn() as db:
        row = db.execute("SELECT payload_json FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    return _enrich_item(NewsItem.model_validate_json(row["payload_json"]))


def get_all_items() -> list[NewsItem]:
    init_db()
    with _conn() as db:
        rows = db.execute("SELECT payload_json FROM items ORDER BY published_at DESC").fetchall()
    return [_enrich_item(NewsItem.model_validate_json(row["payload_json"])) for row in rows]


def save_content_detail(detail: ContentDetail) -> None:
    init_db()
    with _conn() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO content_details
                (item_id, url, normalized_text, retrieved_at, content_hash, content_type, truncated, warnings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                detail.item_id,
                str(detail.url),
                detail.normalized_text,
                _dt_to_ms(detail.retrieved_at),
                detail.content_hash,
                detail.content_type,
                1 if detail.truncated else 0,
                json.dumps(detail.warnings),
            ),
        )
        db.commit()


def get_content_detail(item_id: str) -> ContentDetail | None:
    init_db()
    with _conn() as db:
        row = db.execute("SELECT * FROM content_details WHERE item_id = ?", (item_id,)).fetchone()
    if row is None:
        return None
    return ContentDetail(
        item_id=row["item_id"],
        url=row["url"],
        normalized_text=row["normalized_text"],
        retrieved_at=_ms_to_dt(row["retrieved_at"]),
        content_hash=row["content_hash"],
        content_type=row["content_type"],
        truncated=bool(row["truncated"]),
        warnings=json.loads(row["warnings_json"]),
    )


def get_all_content_details() -> list[ContentDetail]:
    """Return all cached content details (for batch pre-loading)."""
    init_db()
    with _conn() as db:
        rows = db.execute("SELECT * FROM content_details").fetchall()
    return [
        ContentDetail(
            item_id=row["item_id"],
            url=row["url"],
            normalized_text=row["normalized_text"],
            retrieved_at=_ms_to_dt(row["retrieved_at"]),
            content_hash=row["content_hash"],
            content_type=row["content_type"],
            truncated=bool(row["truncated"]),
            warnings=json.loads(row["warnings_json"]),
        )
        for row in rows
    ]


def save_evidence_excerpts(excerpts: list[EvidenceExcerpt]) -> None:
    init_db()
    with _conn() as db:
        db.executemany(
            """
            INSERT OR REPLACE INTO evidence_excerpts
                (evidence_id, item_id, url, title, source_key, source_type, evidence_tier,
                 text, start_char, end_char, retrieved_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    excerpt.evidence_id,
                    excerpt.item_id,
                    str(excerpt.url),
                    excerpt.title,
                    excerpt.source_key,
                    excerpt.source_type.value,
                    excerpt.evidence_tier.value,
                    excerpt.text,
                    excerpt.start_char,
                    excerpt.end_char,
                    _dt_to_ms(excerpt.retrieved_at),
                    excerpt.content_hash,
                )
                for excerpt in excerpts
            ],
        )
        db.commit()


def _evidence_from_row(row: sqlite3.Row) -> EvidenceExcerpt:
    return EvidenceExcerpt(
        evidence_id=row["evidence_id"],
        item_id=row["item_id"],
        url=row["url"],
        title=row["title"],
        source_key=row["source_key"],
        source_type=row["source_type"],
        evidence_tier=row["evidence_tier"],
        text=row["text"],
        start_char=row["start_char"],
        end_char=row["end_char"],
        retrieved_at=_ms_to_dt(row["retrieved_at"]),
        content_hash=row["content_hash"],
    )


def get_evidence(evidence_id: str) -> EvidenceExcerpt | None:
    init_db()
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM evidence_excerpts WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
    return _evidence_from_row(row) if row else None


def get_evidence_many(evidence_ids: list[str]) -> list[EvidenceExcerpt]:
    if not evidence_ids:
        return []
    init_db()
    placeholders = ",".join("?" for _ in evidence_ids)
    with _conn() as db:
        rows = db.execute(
            f"SELECT * FROM evidence_excerpts WHERE evidence_id IN ({placeholders})",
            evidence_ids,
        ).fetchall()
    return [_evidence_from_row(row) for row in rows]


def get_evidence_for_item(item_id: str) -> list[EvidenceExcerpt]:
    init_db()
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM evidence_excerpts WHERE item_id = ? ORDER BY start_char",
            (item_id,),
        ).fetchall()
    return [_evidence_from_row(row) for row in rows]


def search_details(query: str, limit: int) -> list[ContentDetail]:
    init_db()
    escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    with _conn() as db:
        rows = db.execute(
            """
            SELECT * FROM content_details
            WHERE LOWER(normalized_text) LIKE ? ESCAPE '\\'
            ORDER BY retrieved_at DESC
            LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
    return [
        ContentDetail(
            item_id=row["item_id"],
            url=row["url"],
            normalized_text=row["normalized_text"],
            retrieved_at=_ms_to_dt(row["retrieved_at"]),
            content_hash=row["content_hash"],
            content_type=row["content_type"],
            truncated=bool(row["truncated"]),
            warnings=json.loads(row["warnings_json"]),
        )
        for row in rows
    ]


def save_research_session(session: ResearchSession) -> None:
    init_db()
    with _conn() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO research_sessions
                (session_id, title, topic, filters_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.title,
                session.topic,
                json.dumps(session.filters),
                _dt_to_ms(session.created_at),
                _dt_to_ms(session.updated_at),
            ),
        )
        db.commit()


def get_research_session(session_id: str) -> ResearchSession | None:
    init_db()
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM research_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if row is None:
        return None
    return ResearchSession(
        session_id=row["session_id"],
        title=row["title"],
        topic=row["topic"],
        filters=json.loads(row["filters_json"]),
        created_at=_ms_to_dt(row["created_at"]),
        updated_at=_ms_to_dt(row["updated_at"]),
    )


def save_research_note(note: ResearchNote) -> None:
    init_db()
    with _conn() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO research_notes
                (note_id, session_id, text, evidence_ids_json, follow_up, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note.note_id,
                note.session_id,
                note.text,
                json.dumps(note.evidence_ids),
                1 if note.follow_up else 0,
                _dt_to_ms(note.created_at),
            ),
        )
        db.execute(
            "UPDATE research_sessions SET updated_at = ? WHERE session_id = ?",
            (_dt_to_ms(note.created_at), note.session_id),
        )
        db.commit()


def save_research_report(report: ResearchReport) -> None:
    init_db()
    with _conn() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO research_reports
                (report_id, session_id, title, markdown, evidence_ids_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report.report_id,
                report.session_id,
                report.title,
                report.markdown,
                json.dumps(report.evidence_ids),
                _dt_to_ms(report.created_at),
            ),
        )
        db.execute(
            "UPDATE research_sessions SET updated_at = ? WHERE session_id = ?",
            (_dt_to_ms(report.created_at), report.session_id),
        )
        db.commit()


def get_research_notes(session_id: str) -> list[ResearchNote]:
    init_db()
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM research_notes WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [
        ResearchNote(
            note_id=row["note_id"],
            session_id=row["session_id"],
            text=row["text"],
            evidence_ids=json.loads(row["evidence_ids_json"]),
            follow_up=bool(row["follow_up"]),
            created_at=_ms_to_dt(row["created_at"]),
        )
        for row in rows
    ]


def get_research_reports(session_id: str) -> list[ResearchReport]:
    init_db()
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM research_reports WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [
        ResearchReport(
            report_id=row["report_id"],
            session_id=row["session_id"],
            title=row["title"],
            markdown=row["markdown"],
            evidence_ids=json.loads(row["evidence_ids_json"]),
            created_at=_ms_to_dt(row["created_at"]),
        )
        for row in rows
    ]


def get_item_history_since(since: datetime | None, limit: int = 500) -> list[dict[str, object]]:
    init_db()
    since_ms = _dt_to_ms(since) if since else 0
    with _conn() as db:
        rows = db.execute(
            """
            SELECT * FROM item_history
            WHERE first_seen_at >= ? OR last_changed_at >= ?
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (since_ms, since_ms, limit),
        ).fetchall()
    return [
        {
            "item": NewsItem.model_validate_json(row["payload_json"]),
            "first_seen_at": _ms_to_dt(row["first_seen_at"]),
            "last_seen_at": _ms_to_dt(row["last_seen_at"]),
            "last_changed_at": _ms_to_dt(row["last_changed_at"]),
            "content_hash": row["content_hash"],
        }
        for row in rows
    ]


def get_all_snapshots() -> list[SourceHealth]:
    """Return health records for all sources in cache."""
    init_db()
    with _conn() as db:
        rows = db.execute("SELECT * FROM source_snapshots").fetchall()
    return [
        SourceHealth(
            key=row["source_key"],
            status=SourceStatus(row["status"]),
            fetched_at=_ms_to_dt(row["fetched_at"]),
            expires_at=_ms_to_dt(row["expires_at"]),
            item_count=row["item_count"],
            error=row["error"],
        )
        for row in rows
    ]


def _sync_items_fts(db: sqlite3.Connection, source_key: str, items: list[NewsItem]) -> None:
    try:
        db.execute("DELETE FROM items_fts WHERE source_key = ?", (source_key,))
        db.executemany(
            """
            INSERT INTO items_fts
                (id, title, summary, tags, source_key, source_type, evidence_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.id,
                    item.title,
                    item.summary,
                    " ".join(item.tags),
                    item.source_key,
                    item.source_type.value,
                    item.evidence_tier.value,
                )
                for item in items
            ],
        )
    except sqlite3.OperationalError:
        return


def _fts_query(query: str) -> str:
    tokens = re.findall(r"\w+", query.lower())
    if not tokens:
        return '""'
    return " ".join(f"{token}*" for token in tokens[:8])


def _literal_search_items(query: str, limit: int) -> list[NewsItem]:
    escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    with _conn() as db:
        rows = db.execute(
            """
            SELECT payload_json FROM items
            WHERE LOWER(payload_json) LIKE ? ESCAPE '\\'
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
    return [_enrich_item(NewsItem.model_validate_json(row["payload_json"])) for row in rows]


def search_items(query: str, limit: int = 10) -> list[NewsItem]:
    """Ranked search across cached item fields and source metadata."""
    init_db()
    try:
        with _conn() as db:
            rows = db.execute(
                """
                SELECT items.payload_json
                FROM items_fts
                JOIN items ON items.id = items_fts.id
                WHERE items_fts MATCH ?
                ORDER BY
                    bm25(items_fts, 4.0, 2.5, 1.5, 1.0, 0.5, 0.5),
                    items.published_at DESC
                LIMIT ?
                """,
                (_fts_query(query), limit),
            ).fetchall()
        return [_enrich_item(NewsItem.model_validate_json(row["payload_json"])) for row in rows]
    except sqlite3.OperationalError:
        return _literal_search_items(query, limit)
