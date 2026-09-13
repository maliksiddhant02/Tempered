"""CoinGecko — free crypto prices, no API key. A Tempered preset connector.

Public endpoints, rate-limited but keyless, so it runs on start. `vs_currency`
is a real enum the scanner can violate; `trending` takes no input by design.
"""

from typing import Annotated, Literal

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("coingecko")


@mcp.tool()
async def price(
    coin_ids: Annotated[str, Field(min_length=1, max_length=200)],
    vs_currency: Literal["usd", "eur", "gbp", "jpy", "btc"] = "usd",
) -> str:
    """Current price of one or more coins (comma-separated ids, e.g. bitcoin,ethereum)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_ids, "vs_currencies": vs_currency},
        )
        r.raise_for_status()
        return r.text


@mcp.tool()
async def trending() -> str:
    """The coins trending on CoinGecko in the last 24 hours."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get("https://api.coingecko.com/api/v3/search/trending")
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
