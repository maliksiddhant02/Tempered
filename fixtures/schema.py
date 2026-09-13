"""The contract both fixtures declare.

good_server.py enforces it. broken_server.py declares it and ignores it. The
difference between the two is enforcement, never declaration — which is exactly
the drift Tempered exists to detect.
"""

CHARGE_SCHEMA = {
    "type": "object",
    "required": ["amount", "currency"],
    "additionalProperties": False,
    "properties": {
        "amount": {"type": "integer", "minimum": 1, "maximum": 100000},
        "currency": {"type": "string", "enum": ["usd", "eur", "gbp"]},
        "email": {"type": "string", "format": "email"},
        "note": {"type": "string", "maxLength": 40},
    },
}
