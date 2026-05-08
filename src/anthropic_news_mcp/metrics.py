"""Lightweight in-process metrics: counters and timers emitted as structured log lines."""

import logging
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager

_log = logging.getLogger(__name__)

_counters: dict[str, int] = defaultdict(int)


def increment(name: str, value: int = 1) -> None:
    _counters[name] += value


@contextmanager
def timed(name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _log.debug("metric_timer", extra={"metric": name, "elapsed_ms": elapsed_ms})


def record_fetch(source_key: str, item_count: int, elapsed_ms: int, *, success: bool) -> None:
    status = "ok" if success else "error"
    _log.info(
        "source_metric",
        extra={
            "source_key": source_key,
            "item_count": item_count,
            "elapsed_ms": elapsed_ms,
            "status": status,
        },
    )
    increment(f"fetch.{status}")
    increment("fetch.total")


def record_cache_hit(source_key: str) -> None:
    _log.debug("cache_hit", extra={"source_key": source_key})
    increment("cache.hit")


def record_cache_miss(source_key: str) -> None:
    _log.debug("cache_miss", extra={"source_key": source_key})
    increment("cache.miss")


def snapshot() -> dict[str, int]:
    return dict(_counters)
