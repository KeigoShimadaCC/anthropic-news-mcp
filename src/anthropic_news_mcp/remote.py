"""Streamable HTTP ASGI deployment support."""

from __future__ import annotations

import os
from dataclasses import dataclass
from time import time
from typing import Any, cast

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .server import mcp


def _csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class RemoteAuthConfig:
    issuer: str
    audience: str
    required_scopes: list[str]
    allowed_hosts: list[str]
    allowed_origins: list[str]
    resource_server_url: str

    @classmethod
    def from_env(cls) -> RemoteAuthConfig:
        issuer = os.environ.get("ANTHROPIC_NEWS_MCP_AUTH_ISSUER", "").strip()
        audience = os.environ.get("ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE", "").strip()
        allowed_hosts = _csv_env("ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS")
        allowed_origins = _csv_env("ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS")
        required_scopes = _csv_env("ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES")
        resource_server_url = os.environ.get("ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL", "").strip()

        missing = [
            name
            for name, value in {
                "ANTHROPIC_NEWS_MCP_AUTH_ISSUER": issuer,
                "ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE": audience,
                "ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS": ",".join(allowed_hosts),
                "ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS": ",".join(allowed_origins),
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Refusing insecure remote MCP startup; missing required environment: "
                + ", ".join(missing)
            )
        if not required_scopes:
            required_scopes = ["anthropic-news:read"]
        if not resource_server_url:
            resource_server_url = f"https://{allowed_hosts[0]}"
        return cls(
            issuer=issuer,
            audience=audience,
            required_scopes=required_scopes,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
            resource_server_url=resource_server_url,
        )


class OIDCJWTVerifier(TokenVerifier):
    """JWT verifier for resource-server deployments using an external OIDC issuer."""

    def __init__(self, config: RemoteAuthConfig) -> None:
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as exc:  # pragma: no cover - exercised only without remote extra
            raise RuntimeError(
                "Install anthropic-news-mcp[remote] to run Streamable HTTP with OIDC/JWT auth."
            ) from exc

        self._jwt: Any = jwt
        self._jwks = PyJWKClient(f"{config.issuer.rstrip('/')}/.well-known/jwks.json")
        self._config = config

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims = self._jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iat"]},
            )
        except Exception:
            return None

        scopes = _extract_scopes(claims)
        expires_at = claims.get("exp")
        if isinstance(expires_at, int) and expires_at < int(time()):
            return None
        client_id = str(claims.get("client_id") or claims.get("azp") or claims.get("sub") or "")
        if not client_id:
            return None
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at if isinstance(expires_at, int) else None,
            resource=self._config.resource_server_url,
        )


def _extract_scopes(claims: dict[str, Any]) -> list[str]:
    raw_scope = claims.get("scope", "")
    scopes: set[str] = set(raw_scope.split()) if isinstance(raw_scope, str) else set()
    raw_scopes = claims.get("scp", [])
    if isinstance(raw_scopes, str):
        scopes.update(raw_scopes.split())
    elif isinstance(raw_scopes, list):
        scopes.update(str(scope) for scope in raw_scopes)
    return sorted(scopes)


def create_app(config: RemoteAuthConfig | None = None) -> Starlette:
    config = config or RemoteAuthConfig.from_env()
    mcp._session_manager = None  # noqa: SLF001
    mcp._token_verifier = OIDCJWTVerifier(config)  # noqa: SLF001
    mcp.settings.auth = AuthSettings(
        issuer_url=AnyHttpUrl(config.issuer),
        required_scopes=config.required_scopes,
        resource_server_url=AnyHttpUrl(config.resource_server_url),
    )
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=config.allowed_hosts,
        allowed_origins=config.allowed_origins,
    )
    app = mcp.streamable_http_app()
    app.add_middleware(
        HostOriginMiddleware,
        allowed_hosts=set(config.allowed_hosts),
        allowed_origins=set(config.allowed_origins),
    )
    return app


class HostOriginMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        allowed_hosts: set[str],
        allowed_origins: set[str],
    ) -> None:
        super().__init__(app)
        self.allowed_hosts = allowed_hosts
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        host = request.headers.get("host", "").split(":", 1)[0]
        origin = request.headers.get("origin")
        if host and host not in self.allowed_hosts:
            return JSONResponse({"error": "host_not_allowed"}, status_code=403)
        if origin and origin not in self.allowed_origins:
            return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
        response = await call_next(request)
        return cast(Response, response)
