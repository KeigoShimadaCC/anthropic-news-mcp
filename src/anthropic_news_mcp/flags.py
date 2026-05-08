"""Feature flags read from environment variables at import time."""

import os
from dataclasses import dataclass


def _bool_env(key: str, default: bool) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class FeatureFlags:
    enable_metrics_logging: bool = True
    strict_dedup: bool = True
    enable_telemetry: bool = True
    enable_remote_transport: bool = False

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(
            enable_metrics_logging=_bool_env("MCP_METRICS_LOGGING", True),
            strict_dedup=_bool_env("MCP_STRICT_DEDUP", True),
            enable_telemetry=_bool_env("MCP_TELEMETRY", True),
            enable_remote_transport=_bool_env("MCP_REMOTE_TRANSPORT", False),
        )


FLAGS = FeatureFlags.from_env()
