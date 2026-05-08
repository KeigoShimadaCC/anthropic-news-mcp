"""Optional Sentry error tracking. Activated only when SENTRY_DSN env var is set."""

import logging
import os

_log = logging.getLogger(__name__)


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1)
        _log.info("sentry_initialized", extra={"dsn_prefix": dsn[:30]})
    except ImportError:
        _log.debug(
            "sentry_sdk_not_installed",
            extra={"hint": "install anthropic-news-mcp[observability] to enable Sentry"},
        )
