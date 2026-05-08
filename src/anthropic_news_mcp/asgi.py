"""ASGI entrypoint for Streamable HTTP MCP deployments."""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Defer create_app() until 'app' is actually accessed, so missing env vars don't raise at import."""
    if name == "app":
        from .remote import create_app

        return create_app()
    raise AttributeError(name)
