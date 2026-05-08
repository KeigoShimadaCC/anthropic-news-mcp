"""Aggregation, dedup, and orchestration across all sources."""

import asyncio
import logging
import re
import time
from datetime import UTC, datetime
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import cache
from . import metrics as _metrics
from .config import SOURCE_REGISTRY, SourceConfig
from .flags import FLAGS
from .models import Category, EvidenceTier, NewsItem, SourceHealth, SourceStatus, SourceType

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


def _source_rank(item: NewsItem) -> int:
    ranks = {
        SourceType.OFFICIAL: 4,
        SourceType.DOCS: 3,
        SourceType.GITHUB: 2,
        SourceType.COMMUNITY: 1,
    }
    return ranks.get(item.source_type, 0)


def _tier_rank(item: NewsItem) -> int:
    return {EvidenceTier.HIGH: 3, EvidenceTier.MEDIUM: 2, EvidenceTier.LOW: 1}.get(
        item.evidence_tier, 0
    )


def _representative_key(item: NewsItem) -> tuple[int, int, int, int, int, int]:
    summary_quality = min(len(item.summary.strip()), 400)
    registry_order = next(
        (idx for idx, source in enumerate(SOURCE_REGISTRY) if source.key == item.source_key),
        len(SOURCE_REGISTRY),
    )
    return (
        _source_rank(item),
        _tier_rank(item),
        1 if item.published_at is not None else 0,
        item.importance,
        summary_quality,
        -registry_order,
    )


def _sort_dt(item: NewsItem) -> datetime:
    return item.sort_at or item.published_at or item.discovered_at


async def _fetch_source(config: SourceConfig) -> tuple[list[NewsItem], SourceHealth]:
    """Fetch one source with exponential-backoff retry, updating the cache."""
    started = time.perf_counter()
    try:
        fetcher = config.fetcher_cls()
        items: list[NewsItem] = []
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
            reraise=True,
        ):
            with attempt:
                items = await fetcher.fetch()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        cache.save_snapshot(config.key, items, config.ttl_seconds, SourceStatus.LIVE)
        _log.info(
            "source_fetch_succeeded",
            extra={
                "source_key": config.key,
                "item_count": len(items),
                "status": SourceStatus.LIVE.value,
            },
        )
        if FLAGS.enable_metrics_logging:
            _metrics.record_fetch(config.key, len(items), elapsed_ms, success=True)
        health = cache.get_snapshot(config.key)
        if health is None:
            raise RuntimeError(f"Cache write for {config.key!r} did not persist")
        return items, health
    except (Exception, RetryError) as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error_msg = _sanitize_error(exc)
        _log.warning(
            "source_fetch_failed",
            extra={
                "source_key": config.key,
                "error": error_msg,
                "exception_type": type(exc).__name__,
            },
        )
        if FLAGS.enable_metrics_logging:
            _metrics.record_fetch(config.key, 0, elapsed_ms, success=False)
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
            if FLAGS.enable_metrics_logging:
                _metrics.record_cache_hit(config.key)
        else:
            targets_stale.append(config)
            if FLAGS.enable_metrics_logging:
                _metrics.record_cache_miss(config.key)

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

    grouped: dict[str, NewsItem] = {}
    all_healths: list[SourceHealth] = []

    for items, health in [*fresh_results, *stale_results]:
        all_healths.append(health)
        for item in items:
            key = _canonicalize_url(str(item.url)) if FLAGS.strict_dedup else str(item.url)
            existing = grouped.get(key)
            if existing is None or _representative_key(item) > _representative_key(existing):
                grouped[key] = item

    all_items = list(grouped.values())

    # Apply filters
    if categories:
        cat_set = set(categories)
        all_items = [i for i in all_items if cat_set.intersection(i.category)]
    if since:
        all_items = [i for i in all_items if _sort_dt(i) >= since]

    all_items.sort(key=_sort_dt, reverse=True)
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
                    status=SourceStatus.NOT_FETCHED,
                    fetched_at=now,
                    expires_at=now,
                    item_count=0,
                    error="Never fetched",
                )
            )
    return healths
