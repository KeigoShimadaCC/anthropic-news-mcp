import json
import os
import sqlite3
import time
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .models import NewsItem, SourceHealth, SourceStatus

CACHE_SCHEMA_VERSION = 1

_DB_PATH: Path | None = None


def get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is not None:
        return _DB_PATH
    cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    path = Path(cache_home) / "anthropic-news-mcp" / "cache.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.parent.resolve()
    if resolved.stat().st_mode & 0o007:
        warnings.warn(
            f"Cache directory {resolved} is world-readable; "
            "set XDG_CACHE_HOME to a private directory to restrict access.",
            stacklevel=2,
        )
    return path


def set_db_path(path: Path) -> None:
    """Override the default db path — used in tests."""
    global _DB_PATH
    _DB_PATH = path


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    db = sqlite3.connect(str(get_db_path()))
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    with _conn() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        row = db.execute("SELECT version FROM schema_version").fetchone()
        if row and row["version"] != CACHE_SCHEMA_VERSION:
            # Drop and recreate on schema mismatch
            db.execute("DROP TABLE IF EXISTS source_snapshots")
            db.execute("DROP TABLE IF EXISTS items")
            db.execute("DELETE FROM schema_version")

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
        db.execute("CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_key)")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC)"
        )
        db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (CACHE_SCHEMA_VERSION,),
        )
        db.commit()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


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
    return [NewsItem.model_validate(item) for item in raw]


def save_snapshot(
    source_key: str,
    items: list[NewsItem],
    ttl_seconds: int,
    status: SourceStatus = SourceStatus.LIVE,
    error: str | None = None,
) -> None:
    """Persist a fetch result to cache."""
    init_db()
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
        # Also upsert individual item rows for search
        for item in items:
            db.execute(
                """
                INSERT OR REPLACE INTO items
                    (id, source_key, url, published_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.source_key,
                    str(item.url),
                    _dt_to_ms(item.published_at),
                    item.model_dump_json(),
                ),
            )
        db.commit()


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


def search_items(query: str, limit: int = 10) -> list[NewsItem]:
    """Case-insensitive substring search across title, summary, and tags."""
    init_db()
    # Escape LIKE metacharacters so user input is treated as a literal substring,
    # not a wildcard pattern. Without this, query="_" matches every row.
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
    return [NewsItem.model_validate_json(row["payload_json"]) for row in rows]
