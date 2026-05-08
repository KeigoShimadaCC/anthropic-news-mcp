import httpx
import pytest

from anthropic_news_mcp.http import get_client


@pytest.mark.asyncio
async def test_get_client_blocks_unapproved_final_host() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text="blocked")

    async with get_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPError, match="Blocked response host"):
            await client.get("https://evil.example/news")
