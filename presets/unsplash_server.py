"""Unsplash — photo search. A Tempered preset connector.

Reads UNSPLASH_ACCESS_KEY from the environment (the "Access Key" from your
Unsplash app — never the secret key). Set it in .env or the demo's Keys panel.
"""

import os
from typing import Annotated

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("unsplash")


@mcp.tool()
async def search_photos(
    query: Annotated[str, Field(min_length=1, max_length=100)],
    per_page: Annotated[int, Field(ge=1, le=30)] = 5,
) -> str:
    """Search Unsplash for photos matching a query; returns image URLs and credits."""
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        raise RuntimeError("UNSPLASH_ACCESS_KEY is not set — add it in Keys or .env")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": per_page},
            headers={"Authorization": f"Client-ID {key}"},
        )
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
