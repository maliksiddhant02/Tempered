"""GitHub REST API. A Tempered preset connector.

Reads are keyless (rate-limited); set GITHUB_TOKEN in Keys or .env to raise the
limit and to open issues. `create_issue` writes, so the scanner skips it unless
you pass --allow-writes (see github_server_methods.json).
"""

import os
from typing import Annotated

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("github")

BASE = "https://api.github.com"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "tempered-preset"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


@mcp.tool()
async def search_repos(
    query: Annotated[str, Field(min_length=1, max_length=256)],
    per_page: Annotated[int, Field(ge=1, le=100)] = 5,
) -> str:
    """Search public repositories (e.g. 'language:python stars:>1000')."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{BASE}/search/repositories",
            params={"q": query, "per_page": per_page},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.text


@mcp.tool()
async def get_user(username: Annotated[str, Field(min_length=1, max_length=39)]) -> str:
    """Public profile for a GitHub username."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{BASE}/users/{username}", headers=_headers())
        r.raise_for_status()
        return r.text


@mcp.tool()
async def create_issue(
    owner: Annotated[str, Field(min_length=1, max_length=39)],
    repo: Annotated[str, Field(min_length=1, max_length=100)],
    title: Annotated[str, Field(min_length=1, max_length=256)],
    body: str = "",
) -> str:
    """Open an issue on owner/repo. Requires GITHUB_TOKEN with repo scope."""
    if not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN is not set — add it in Keys or .env")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{BASE}/repos/{owner}/{repo}/issues",
            json={"title": title, "body": body},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    mcp.run()
