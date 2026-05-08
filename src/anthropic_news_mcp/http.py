import httpx

from . import __version__

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_HEADERS = {
    "User-Agent": f"anthropic-news-mcp/{__version__} (+https://github.com/KeigoShimadaCC/anthropic-news-mcp)"
}
_ALLOWED_FETCH_HOSTS = {
    "api.github.com",
    "anthropic.com",
    "claude.ai",
    "docs.anthropic.com",
    "docs.claude.com",
    "hn.algolia.com",
    "platform.claude.com",
    "raw.githubusercontent.com",
    "reddit.com",
    "status.claude.com",
    "support.claude.com",
    "www.reddit.com",
}


async def _validate_response_host(response: httpx.Response) -> None:
    host = response.url.host
    if host not in _ALLOWED_FETCH_HOSTS:
        raise httpx.RequestError(f"Blocked response host {host!r}", request=response.request)


def get_client(**kwargs: object) -> httpx.AsyncClient:
    """Return a configured async httpx client. Caller is responsible for closing."""
    event_hooks = kwargs.pop("event_hooks", {})
    if not isinstance(event_hooks, dict):
        event_hooks = {}
    response_hooks = list(event_hooks.get("response", []))
    response_hooks.append(_validate_response_host)
    event_hooks["response"] = response_hooks
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers=_HEADERS,
        follow_redirects=True,
        max_redirects=5,
        event_hooks=event_hooks,
        **kwargs,  # type: ignore[arg-type]
    )
