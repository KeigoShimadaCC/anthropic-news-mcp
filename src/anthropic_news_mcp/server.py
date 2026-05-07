from mcp.server.fastmcp import FastMCP

from . import __version__

mcp = FastMCP("anthropic-news")


@mcp.tool()
async def ping() -> dict[str, str]:
    """Health check. Returns ok status and server version."""
    return {"status": "ok", "server": "anthropic-news-mcp", "version": __version__}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
