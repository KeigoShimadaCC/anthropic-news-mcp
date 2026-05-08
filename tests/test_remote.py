import sys
import types
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from mcp.server.auth.provider import AccessToken

from anthropic_news_mcp.remote import OIDCJWTVerifier, RemoteAuthConfig, _extract_scopes, create_app


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


def test_extract_scopes_accepts_scope_and_scp_claims() -> None:
    assert _extract_scopes({"scope": "beta alpha", "scp": ["gamma", "alpha"]}) == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert _extract_scopes({"scp": "delta epsilon"}) == ["delta", "epsilon"]


def test_remote_env_defaults_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_NEWS_MCP_AUTH_ISSUER", "https://issuer.example")
    monkeypatch.setenv("ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE", "anthropic-news")
    monkeypatch.setenv("ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS", " testserver, api.example ")
    monkeypatch.setenv("ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS", " https://client.example ")
    monkeypatch.delenv("ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES", raising=False)
    monkeypatch.delenv("ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL", raising=False)

    config = RemoteAuthConfig.from_env()

    assert config.required_scopes == ["anthropic-news:read"]
    assert config.allowed_hosts == ["testserver", "api.example"]
    assert config.allowed_origins == ["https://client.example"]
    assert config.resource_server_url == "https://testserver"


@pytest.fixture
def fake_jwt_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = types.ModuleType("jwt")

    class FakePyJWKClient:
        def __init__(self, url: str) -> None:
            self.url = url

        def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
            if token == "keyfail":
                raise RuntimeError("jwks unavailable")
            return SimpleNamespace(key="public-key")

    def decode(
        token: str,
        key: str,
        *,
        algorithms: list[str],
        audience: str,
        issuer: str,
        options: dict[str, list[str]],
    ) -> dict[str, Any]:
        assert key == "public-key"
        assert algorithms == ["RS256", "ES256"]
        assert audience == "anthropic-news"
        assert issuer == "https://issuer.example"
        assert options == {"require": ["exp", "iat"]}
        if token == "baddecode":
            raise RuntimeError("invalid token")
        if token == "no-client":
            return {"scope": "anthropic-news:read", "exp": 1770000000, "iat": 1760000000}
        return {
            "scope": "anthropic-news:read extra",
            "scp": ["anthropic-news:read"],
            "client_id": "client-1",
            "exp": 1770000000,
            "iat": 1760000000,
        }

    module.PyJWKClient = FakePyJWKClient  # type: ignore[attr-defined]
    module.decode = decode  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "jwt", module)
    return module


@pytest.mark.asyncio
async def test_oidc_jwt_verifier_success(
    remote_config: RemoteAuthConfig,
    fake_jwt_module: types.ModuleType,
) -> None:
    verifier = OIDCJWTVerifier(remote_config)

    token = await verifier.verify_token("good")

    assert token is not None
    assert token.client_id == "client-1"
    assert token.scopes == ["anthropic-news:read", "extra"]
    assert token.expires_at == 1770000000
    assert token.resource == "https://testserver"


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_token", ["keyfail", "baddecode", "no-client"])
async def test_oidc_jwt_verifier_rejects_invalid_tokens(
    raw_token: str,
    remote_config: RemoteAuthConfig,
    fake_jwt_module: types.ModuleType,
) -> None:
    verifier = OIDCJWTVerifier(remote_config)

    token = await verifier.verify_token(raw_token)

    assert token is None
