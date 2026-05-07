import httpx

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_HEADERS = {
    "User-Agent": "anthropic-news-mcp/0.1.0 (+https://github.com/KeigoShimadaCC/anthropic-news-mcp)"
}


def get_client(**kwargs: object) -> httpx.AsyncClient:
    """Return a configured async httpx client. Caller is responsible for closing."""
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers=_HEADERS,
        follow_redirects=True,
        **kwargs,  # type: ignore[arg-type]
    )
