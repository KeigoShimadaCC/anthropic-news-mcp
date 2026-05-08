"""Aggregation, dedup, and orchestration across all sources."""

import asyncio
import logging
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

from . import cache
from .config import SOURCE_REGISTRY, SourceConfig
from .models import Category, NewsItem, SourceHealth, SourceStatus

_log = logging.getLogger(__name__)
_UTM_RE = re.compile(r"utm_[a-z_]+", re.IGNORECASE)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization:\s*bearer\s+)[^\s,;]+|"
    r"((?:api[_-]?key|access[_-]?token|auth[_-]?token|id[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|password|secret|token)=)[^&\s,;]+"
)


def _canonicalize_url(url: str) -> str:
    """Normalize URL for dedup: drop fragments, utm_* params, decode and sort remaining params."""
    parsed = urlparse(url)
    params = [(unquote(k), unquote(v)) for k, v in parse_qsl(parsed.query) if not _UTM_RE.match(k)]
    params.sort()
    normalized = parsed._replace(fragment="", query=urlencode(params))
    return urlunparse(normalized)


def _sanitize_error(exc: Exception) -> str:
    """Truncate error string and strip secrets from URLs, headers, and key/value text."""
    msg = re.sub(r"\?[^\s]*", "?[redacted]", str(exc))
    msg = _SECRET_VALUE_RE.sub(
        lambda match: f"{match.group(1) or match.group(2)}[redacted]",
        msg,
    )
    return msg[:200]


async def _fetch_source(config: SourceConfig) -> tuple[list[NewsItem], SourceHealth]:
    """Fetch one source, updating the cache. Returns (items, health)."""
    try:
        fetcher = config.fetcher_cls()
        items = await fetcher.fetch()
        cache.save_snapshot(config.key, items, config.ttl_seconds, SourceStatus.LIVE)
        health = cache.get_snapshot(config.key)
        if health is None:
            raise RuntimeError(f"Cache write for {config.key!r} did not persist")
        return items, health
    except Exception as exc:
        error_msg = _sanitize_error(exc)
        _log.warning("fetch failed for %r: %s", config.key, error_msg)
        # Preserve last-known items from cache even on failure
        cached_items = cache.get_cached_items(config.key)
        status = SourceStatus.STALE if cached_items else SourceStatus.DOWN
        cache.save_snapshot(
            config.key,
            cached_items,
            0,
            status=status,
            error=error_msg,
        )
        health = cache.get_snapshot(config.key)
        if health is None:
            raise RuntimeError(f"Cache write for {config.key!r} did not persist") from exc
        return cached_items, health


async def get_recent_updates(
    sources: list[str] | None = None,
    categories: list[Category] | None = None,
    since: datetime | None = None,
    limit: int = 20,
) -> tuple[list[NewsItem], list[SourceHealth]]:
    """Aggregate items from all (or selected) sources, with caching."""
    registry = SOURCE_REGISTRY
    if sources:
        key_set = set(sources)
        registry = [s for s in registry if s.key in key_set]

    targets_fresh: list[SourceConfig] = []
    targets_stale: list[SourceConfig] = []

    for config in registry:
        if not config.enabled:
            continue
        if cache.is_fresh(config.key):
            targets_fresh.append(config)
        else:
            targets_stale.append(config)

    # Fetch stale/missing sources concurrently
    stale_results: list[tuple[list[NewsItem], SourceHealth]] = []
    if targets_stale:
        results = await asyncio.gather(
            *[_fetch_source(c) for c in targets_stale], return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                _log.warning("_fetch_source raised unexpectedly: %r", type(result).__name__)
                continue
            stale_results.append(result)

    # Pull fresh sources from cache
    fresh_results: list[tuple[list[NewsItem], SourceHealth]] = []
    for config in targets_fresh:
        items = cache.get_cached_items(config.key)
        health = cache.get_snapshot(config.key)
        if health:
            # Mark as cache status (not live)
            health = health.model_copy(update={"status": SourceStatus.CACHE})
        else:
            now = datetime.now(tz=UTC)
            health = SourceHealth(
                key=config.key,
                status=SourceStatus.CACHE,
                fetched_at=now,
                expires_at=now,
                item_count=len(items),
            )
        fresh_results.append((items, health))

    all_items: list[NewsItem] = []
    all_healths: list[SourceHealth] = []
    seen_urls: set[str] = set()

    for items, health in [*fresh_results, *stale_results]:
        all_healths.append(health)
        for item in items:
            canonical = _canonicalize_url(str(item.url))
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)
            all_items.append(item)

    # Apply filters
    if categories:
        cat_set = set(categories)
        all_items = [i for i in all_items if cat_set.intersection(i.category)]
    if since:
        all_items = [i for i in all_items if i.published_at >= since]

    all_items.sort(key=lambda x: x.published_at, reverse=True)
    return all_items[:limit], all_healths


async def search_updates(query: str, limit: int = 10) -> list[NewsItem]:
    if not cache.get_all_snapshots():
        await get_recent_updates(limit=max(limit, 1))
    return cache.search_items(query, limit)


async def get_health() -> list[SourceHealth]:
    """Return health for all configured sources, with placeholders for uncached ones."""

    cached = {h.key: h for h in cache.get_all_snapshots()}
    healths: list[SourceHealth] = []
    now = datetime.now(tz=UTC)
    for config in SOURCE_REGISTRY:
        if config.key in cached:
            healths.append(cached[config.key])
        else:
            healths.append(
                SourceHealth(
                    key=config.key,
                    status=SourceStatus.DOWN,
                    fetched_at=now,
                    expires_at=now,
                    item_count=0,
                    error="Never fetched",
                )
            )
    return healths
