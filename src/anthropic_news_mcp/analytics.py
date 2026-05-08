"""Optional PostHog product analytics — no-op when POSTHOG_API_KEY is unset."""

import logging
import os

_log = logging.getLogger(__name__)
_initialised = False


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


def capture(event: str, properties: dict[str, object] | None = None) -> None:
    if not _initialised:
        return
    try:
        import posthog
        posthog.capture("anonymous", event, properties or {})
    except Exception:
        pass
