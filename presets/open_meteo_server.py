"""Open-Meteo — free weather, no API key. A Tempered preset connector.

Hand-written FastMCP tools with real, enforced schemas: the calling agent gets
current conditions and place->coordinates lookup, and Tempered's scan can attack
every declared constraint. No auth, so it works the moment the server starts.
"""

from typing import Annotated

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("open-meteo")


@mcp.tool()
async def current_weather(
    latitude: Annotated[float, Field(ge=-90, le=90)],
    longitude: Annotated[float, Field(ge=-180, le=180)],
) -> str:
    """Current temperature, wind and weather code for a latitude/longitude."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": latitude, "longitude": longitude, "current_weather": "true"},
        )
        r.raise_for_status()
        return r.text


@mcp.tool()
async def geocode(name: Annotated[str, Field(min_length=1, max_length=100)]) -> str:
    """Look up coordinates for a place name (feed the result to current_weather)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 5},
        )
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
