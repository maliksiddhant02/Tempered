"""Pollinations — free AI image and text generation, no API key. Preset connector.

`image` returns a ready-to-open image URL (built, not fetched, so it is instant);
`text` calls the keyless text endpoint for a real round trip.
"""

from typing import Annotated
from urllib.parse import quote

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("pollinations")


@mcp.tool()
async def image(
    prompt: Annotated[str, Field(min_length=1, max_length=500)],
    width: Annotated[int, Field(ge=64, le=2048)] = 1024,
    height: Annotated[int, Field(ge=64, le=2048)] = 1024,
    seed: Annotated[int, Field(ge=0, le=999999)] = 42,
) -> str:
    """Generate an AI image from a text prompt; returns a URL you can open."""
    return (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width={width}&height={height}&seed={seed}&nologo=true"
    )


@mcp.tool()
async def text(prompt: Annotated[str, Field(min_length=1, max_length=500)]) -> str:
    """Generate a short AI text completion for a prompt."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"https://text.pollinations.ai/{quote(prompt)}")
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
