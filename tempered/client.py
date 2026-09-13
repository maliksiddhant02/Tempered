"""MCP protocol client — spawn a server over stdio, list its tools, call them.

Thin wrapper over the official SDK. Its only real job is turning every possible
outcome of a tool call into one of four verdicts the checks can reason about.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

CALL_TIMEOUT_SECONDS = 20.0

# The four verdicts. A conformant server rejects invalid input with ERROR.
ERROR = "error"  # JSON-RPC error or isError: true -- correct rejection
OK = "ok"  # normal success result
CRASH = "crash"  # timeout, transport failure, server died


@dataclass(frozen=True)
class ToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Outcome:
    """What a server did when we called one of its tools."""

    kind: str  # ERROR | OK | CRASH
    text: str  # response text or failure reason, truncated

    @property
    def rejected(self) -> bool:
        return self.kind == ERROR


class Server:
    """A connected MCP server."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def tools(self) -> list[ToolInfo]:
        result = await self._session.list_tools()
        return [
            ToolInfo(
                name=t.name,
                description=t.description or "",
                input_schema=t.input_schema or {},
            )
            for t in result.tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> Outcome:
        """Call a tool and classify the result. Never raises."""
        try:
            result = await self._session.call_tool(
                name, arguments, read_timeout_seconds=CALL_TIMEOUT_SECONDS
            )
        except MCPError as exc:
            # Protocol-level rejection: the server said no properly.
            return Outcome(ERROR, _clip(str(exc)))
        except Exception as exc:  # noqa: BLE001 - transport death, timeout, anything
            return Outcome(CRASH, f"{type(exc).__name__}: {_clip(str(exc))}")

        if getattr(result, "is_error", False):
            return Outcome(ERROR, _clip(_render(result)))
        return Outcome(OK, _clip(_render(result)))


@asynccontextmanager
async def connect(
    command: str, args: list[str] | None = None, env: dict[str, str] | None = None
) -> AsyncIterator[Server]:
    """Spawn an MCP server over stdio and hand back a connected session."""
    params = StdioServerParameters(command=command, args=args or [], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield Server(session)


def _render(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", None) or []:
        parts.append(getattr(block, "text", None) or repr(block))
    if not parts and getattr(result, "structured_content", None):
        parts.append(repr(result.structured_content))
    return " ".join(parts)


def _clip(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."
