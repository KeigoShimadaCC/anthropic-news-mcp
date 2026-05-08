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


@pytest.mark.asyncio
async def test_get_client_allows_approved_host() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text="ok")

    async with get_client(transport=httpx.MockTransport(handler)) as client:
        response = await client.get("https://www.anthropic.com/news")

    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_get_client_blocks_redirect_to_unapproved_host() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.anthropic.com":
            return httpx.Response(
                302,
                request=request,
                headers={"location": "https://evil.example/news"},
            )
        return httpx.Response(200, request=request, text="blocked")

    async with get_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPError, match="Blocked response host"):
            await client.get("https://www.anthropic.com/news")


@pytest.mark.asyncio
async def test_get_client_preserves_caller_response_hooks() -> None:
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text="ok")

    async def response_hook(response: httpx.Response) -> None:
        seen.append(str(response.url))

    async with get_client(
        transport=httpx.MockTransport(handler),
        event_hooks={"response": [response_hook]},
    ) as client:
        await client.get("https://www.anthropic.com/news")

    assert seen == ["https://www.anthropic.com/news"]
