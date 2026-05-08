"""Streamable HTTP ASGI deployment support."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .server import mcp

_log = logging.getLogger(__name__)


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
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 30

    @classmethod
    def from_env(cls) -> RemoteAuthConfig:
        issuer = os.environ.get("ANTHROPIC_NEWS_MCP_AUTH_ISSUER", "").strip()
        audience = os.environ.get("ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE", "").strip()
        allowed_hosts = _csv_env("ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS")
        allowed_origins = _csv_env("ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS")
        required_scopes = _csv_env("ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES")
        resource_server_url = os.environ.get("ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL", "").strip()
        rate_limit_per_minute = int(
            os.environ.get("ANTHROPIC_NEWS_MCP_RATE_LIMIT_PER_MINUTE", "120")
        )
        rate_limit_burst = int(os.environ.get("ANTHROPIC_NEWS_MCP_RATE_LIMIT_BURST", "30"))

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
            rate_limit_per_minute=max(rate_limit_per_minute, 1),
            rate_limit_burst=max(rate_limit_burst, 1),
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
        loop = asyncio.get_event_loop()
        try:
            signing_key = await loop.run_in_executor(
                None, self._jwks.get_signing_key_from_jwt, token
            )
        except Exception:
            _log.warning(
                "JWKS key lookup failed — all tokens will be rejected until resolved",
                exc_info=True,
            )
            return None
        try:
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
    app.add_middleware(
        RequestLogRateLimitMiddleware,
        rate_limit_per_minute=config.rate_limit_per_minute,
        rate_limit_burst=config.rate_limit_burst,
    )
    return app


class _TokenBucket:
    def __init__(self, *, rate_per_minute: int, burst: int) -> None:
        self.rate_per_second = rate_per_minute / 60
        self.burst = float(burst)
        self.tokens: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, updated_at = self.tokens.get(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - updated_at) * self.rate_per_second)
        if tokens < 1:
            self.tokens[key] = (tokens, now)
            return False
        self.tokens[key] = (tokens - 1, now)
        return True


class RequestLogRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        rate_limit_per_minute: int,
        rate_limit_burst: int,
    ) -> None:
        super().__init__(app)
        self.bucket = _TokenBucket(
            rate_per_minute=rate_limit_per_minute,
            burst=rate_limit_burst,
        )

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("x-request-id") or uuid4().hex
        client = request.client.host if request.client else "unknown"
        if not self.bucket.allow(client):
            _log.info(
                "remote_request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 429,
                    "client": client,
                },
            )
            return JSONResponse(
                {"error": {"code": "rate_limited", "message": "Too many requests.", "details": {}}},
                status_code=429,
                headers={"x-request-id": request_id},
            )
        started = time.perf_counter()
        response = cast(Response, await call_next(request))
        response.headers["x-request-id"] = request_id
        _log.info(
            "remote_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "client": client,
            },
        )
        return response


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
        request_id = request.headers.get("x-request-id") or uuid4().hex
        if host and host not in self.allowed_hosts:
            _log.warning(
                "remote_request_denied",
                extra={
                    "request_id": request_id,
                    "reason": "host_not_allowed",
                    "host": host,
                    "origin": origin,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                {
                    "error": {
                        "code": "host_not_allowed",
                        "message": "Host is not allowed.",
                        "details": {},
                    }
                },
                status_code=403,
                headers={"x-request-id": request_id},
            )
        if origin and origin not in self.allowed_origins:
            _log.warning(
                "remote_request_denied",
                extra={
                    "request_id": request_id,
                    "reason": "origin_not_allowed",
                    "host": host,
                    "origin": origin,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                {
                    "error": {
                        "code": "origin_not_allowed",
                        "message": "Origin is not allowed.",
                        "details": {},
                    }
                },
                status_code=403,
                headers={"x-request-id": request_id},
            )
        response = await call_next(request)
        return cast(Response, response)
