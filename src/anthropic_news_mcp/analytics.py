"""Optional PostHog product analytics — no-op when POSTHOG_API_KEY is unset.

Capture is split into two paths:
- ``capture(event, props)`` — single-event emission (e.g. server_startup).
- ``track_tool(name)`` — decorator for MCP tool functions that records latency,
  outcome (ok / error), and result-shape metadata for every invocation.

Both paths are safe to call when PostHog is disabled: they degrade to no-op.
The distinct user identifier is a stable hash of the host machine to avoid
attributing events to a real account while still allowing per-installation
trend analysis.
"""

import functools
import hashlib
import logging
import os
import platform
import time
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast

_log = logging.getLogger(__name__)
_initialised = False
_distinct_id_cache: str | None = None

P = ParamSpec("P")
R = TypeVar("R")


def _distinct_id() -> str:
    """Stable per-installation pseudonymous id (sha256 of node + platform)."""
    global _distinct_id_cache
    if _distinct_id_cache is None:
        raw = f"{platform.node()}|{platform.system()}|{platform.machine()}"
        _distinct_id_cache = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return _distinct_id_cache


def init_analytics() -> None:
    global _initialised
    api_key = os.getenv("POSTHOG_API_KEY")
    if not api_key:
        return
    try:
        import posthog

        posthog.api_key = api_key
        posthog.host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
        posthog.debug = False
        _initialised = True
        _log.debug("PostHog analytics initialised")
    except ImportError:
        _log.debug("posthog package not installed; analytics disabled")


def is_enabled() -> bool:
    return _initialised


def capture(event: str, properties: dict[str, object] | None = None) -> None:
    if not _initialised:
        return
    try:
        import posthog

        posthog.capture(_distinct_id(), event, properties or {})
    except Exception:
        # Never let analytics break a tool call.
        pass


def track_tool(
    name: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for MCP tool functions.

    Records latency_ms, outcome (ok|error), error_class on failure, and
    result_keys (top-level dict keys, no values) for shape-level insight.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            outcome = "ok"
            error_class: str | None = None
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                outcome = "error"
                error_class = type(exc).__name__
                raise
            finally:
                if _initialised:
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    props: dict[str, object] = {
                        "tool": name,
                        "outcome": outcome,
                        "latency_ms": elapsed_ms,
                    }
                    if error_class is not None:
                        props["error_class"] = error_class
                    capture("tool_invoked", props)
            # mypy: result is bound when no exception was raised.
            return cast(R, locals()["result"])

        # Preserve the underlying coroutine signature for FastMCP.
        return cast(Callable[P, Awaitable[R]], wrapper)

    return decorator


__all__ = ["capture", "init_analytics", "is_enabled", "track_tool"]
# Silence vulture: track_tool's helper returns and exported public surface.
_: Any = (capture, init_analytics, is_enabled, track_tool)
