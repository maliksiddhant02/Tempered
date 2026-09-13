"""Known-good MCP server — the false-positive control.

Declares a strict schema AND enforces it. Tempered must pass this cleanly; a
harness that flags a correct server is worse than no harness at all.

Run: python fixtures/good_server.py
"""

from fastmcp import FastMCP
from fastmcp.tools import Tool

from schema import CHARGE_SCHEMA

mcp = FastMCP("good-payments")

CURRENCIES = CHARGE_SCHEMA["properties"]["currency"]["enum"]
MAX_NOTE = CHARGE_SCHEMA["properties"]["note"]["maxLength"]


def create_charge(
    amount: object = None,
    currency: object = None,
    email: object = "user@example.com",
    note: object = "",
) -> str:
    """Charge a customer. Validates every declared constraint by hand.

    Arguments are deliberately untyped so that validation is visible here rather
    than hidden in pydantic — this is the behaviour under test, so it should be
    readable.
    """
    if amount is None:
        raise ValueError("amount is required")
    if currency is None:
        raise ValueError("currency is required")

    # bool is a subclass of int; reject it explicitly.
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError(f"amount must be an integer, got {type(amount).__name__}")
    if not 1 <= amount <= 100000:
        raise ValueError(f"amount {amount} out of range 1..100000")

    if not isinstance(currency, str):
        raise ValueError(f"currency must be a string, got {type(currency).__name__}")
    if currency not in CURRENCIES:
        raise ValueError(f"currency {currency!r} not one of {CURRENCIES}")

    if not isinstance(email, str):
        raise ValueError(f"email must be a string, got {type(email).__name__}")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError(f"email is not a valid address: {email!r}")

    if not isinstance(note, str):
        raise ValueError(f"note must be a string, got {type(note).__name__}")
    if len(note) > MAX_NOTE:
        raise ValueError(f"note longer than {MAX_NOTE} characters")

    return f"charged {amount} {currency} to {email}"


tool = Tool.from_function(
    create_charge, name="create_charge", description="Charge a customer a fixed amount."
)
tool.parameters = CHARGE_SCHEMA
mcp.add_tool(tool)


if __name__ == "__main__":
    mcp.run()
