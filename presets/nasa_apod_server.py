"""NASA APOD — Astronomy Picture of the Day. A Tempered preset connector.

Reads NASA_API_KEY from the environment and falls back to NASA's shared
DEMO_KEY, so it works with no setup (DEMO_KEY just has a tight rate limit — set
your own key in .env for a busy demo).
"""

import os
import re
from typing import Annotated

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("nasa-apod")

API = "https://api.nasa.gov/planetary/apod"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _key() -> str:
    return os.environ.get("NASA_API_KEY") or "DEMO_KEY"


@mcp.tool()
async def apod(date: str = "") -> str:
    """Astronomy Picture of the Day. Optional date as YYYY-MM-DD; empty means today."""
    if date and not _DATE.match(date):
        raise ValueError("date must be YYYY-MM-DD")
    params = {"api_key": _key()}
    if date:
        params["date"] = date
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(API, params=params)
        r.raise_for_status()
        return r.text


@mcp.tool()
async def apod_random(count: Annotated[int, Field(ge=1, le=10)] = 1) -> str:
    """A random selection of Astronomy Pictures of the Day (1 to 10 of them)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(API, params={"api_key": _key(), "count": count})
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
