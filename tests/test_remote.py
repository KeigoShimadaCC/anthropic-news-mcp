from typing import Any

import httpx
import pytest
from mcp.server.auth.provider import AccessToken

from anthropic_news_mcp.remote import RemoteAuthConfig, create_app


class StaticVerifier:
    def __init__(self, config: RemoteAuthConfig) -> None:
        self.config = config

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == "good":
            return AccessToken(
                token=token,
                client_id="client",
                scopes=["anthropic-news:read"],
                resource=self.config.resource_server_url,
            )
        if token == "noscope":
            return AccessToken(
                token=token,
                client_id="client",
                scopes=[],
                resource=self.config.resource_server_url,
            )
        return None


@pytest.fixture
def remote_config() -> RemoteAuthConfig:
    return RemoteAuthConfig(
        issuer="https://issuer.example",
        audience="anthropic-news",
        required_scopes=["anthropic-news:read"],
        allowed_hosts=["testserver"],
        allowed_origins=["https://client.example"],
        resource_server_url="https://testserver",
    )


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, remote_config: RemoteAuthConfig) -> Any:
    monkeypatch.setattr("anthropic_news_mcp.remote.OIDCJWTVerifier", StaticVerifier)
    return create_app(remote_config)


@pytest.mark.asyncio
async def test_remote_requires_auth_and_scope(app: Any) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/mcp")
        assert response.status_code == 401
        assert "resource_metadata" in response.headers["www-authenticate"]

        response = await client.post("/mcp", headers={"Authorization": "Bearer bad"})
        assert response.status_code == 401

        response = await client.post("/mcp", headers={"Authorization": "Bearer noscope"})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_remote_valid_scoped_token_can_initialize(app: Any) -> None:
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    headers = {
        "authorization": "Bearer good",
        "origin": "https://client.example",
        "accept": "application/json, text/event-stream",
    }
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.post("/mcp", headers=headers, json=initialize)

    assert response.status_code == 200
    assert "anthropic-news" in response.text


@pytest.mark.asyncio
async def test_remote_rejects_bad_origin_and_host(app: Any) -> None:
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.post(
            "/mcp",
            headers={
                "authorization": "Bearer good",
                "origin": "https://bad.example",
                "content-type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 403

        response = await client.post(
            "http://evil.example/mcp",
            headers={
                "authorization": "Bearer good",
                "origin": "https://client.example",
                "content-type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_remote_protected_resource_metadata(app: Any) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/.well-known/oauth-protected-resource")

    assert response.status_code == 200
    data = response.json()
    assert data["authorization_servers"] == ["https://issuer.example/"]
    assert data["scopes_supported"] == ["anthropic-news:read"]


def test_remote_env_refuses_insecure_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "ANTHROPIC_NEWS_MCP_AUTH_ISSUER",
        "ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE",
        "ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS",
        "ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="Refusing insecure remote MCP startup"):
        RemoteAuthConfig.from_env()
