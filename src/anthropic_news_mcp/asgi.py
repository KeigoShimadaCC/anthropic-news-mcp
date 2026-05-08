"""ASGI entrypoint for Streamable HTTP MCP deployments."""

from .remote import create_app

app = create_app()
