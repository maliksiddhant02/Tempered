"""Discord — post a message via an incoming webhook. A Tempered preset connector.

Reads DISCORD_WEBHOOK_URL from the environment. This tool writes, so the scanner
skips it unless you pass --allow-writes (see discord_server_methods.json).
"""

import os
from typing import Annotated

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("discord")


@mcp.tool()
async def post_message(
    content: Annotated[str, Field(min_length=1, max_length=2000)],
    username: Annotated[str, Field(max_length=80)] = "",
) -> str:
    """Post a message to the configured Discord channel via its incoming webhook."""
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set — add it in Keys or .env")
    payload: dict[str, str] = {"content": content}
    if username:
        payload["username"] = username
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return f"posted ({r.status_code})"


if __name__ == "__main__":
    mcp.run()
