"""Deliberately broken MCP server — the thing Tempered is built to catch.

Declares exactly the same contract as good_server.py and enforces none of it.
Every call returns a cheerful success string, so the calling agent believes the
charge went through no matter what it sent. Nothing lands in error monitoring.

This is not a strawman. It is what you get by wrapping an API in a try/except
and returning the friendliest thing you can think of.

Run: python fixtures/broken_server.py
"""

from fastmcp import FastMCP
from fastmcp.tools import Tool

from schema import CHARGE_SCHEMA

mcp = FastMCP("broken-payments")


def create_charge(
    amount: object = None,
    currency: object = None,
    email: object = "user@example.com",
    note: object = "",
) -> str:
    """Charge a customer. Validates nothing, fails never."""
    try:
        return f"charged {amount} {currency} to {email}"
    except Exception:  # noqa: BLE001 - the bug, faithfully reproduced
        return "OK"


tool = Tool.from_function(
    create_charge, name="create_charge", description="Charge a customer a fixed amount."
)
tool.parameters = CHARGE_SCHEMA
mcp.add_tool(tool)


if __name__ == "__main__":
    mcp.run()
