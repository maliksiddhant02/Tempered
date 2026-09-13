"""Notion connector — hand-written, not generated.

Notion's "append to a page" endpoint takes a deeply nested block structure that
does not map to a flat drafted field, so this adapter exposes a clean
`append_note(page_id, text)` tool and builds the nested body itself.

Unlike the from_openapi connectors, this one ENFORCES its declared schema (the
good_server pattern): validate every constraint by hand, raise on violation.
That is deliberate — run `tempered test` against it and it should score well,
the positive control beside the generated connectors that do not validate.
"""

import os

import httpx2 as httpx
from fastmcp import FastMCP
from fastmcp.tools import Tool

mcp = FastMCP("notion")

NOTE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_id", "text"],
    "properties": {
        "page_id": {"type": "string", "minLength": 1, "description": "The Notion page to append to."},
        "text": {"type": "string", "minLength": 1, "maxLength": 2000, "description": "The update text."},
    },
}


def append_note(page_id: object = None, text: object = None) -> str:
    """Append a paragraph to a Notion page. Untyped args so validation is visible."""
    if not isinstance(page_id, str) or not page_id:
        raise ValueError("page_id is required and must be a non-empty string")
    if not isinstance(text, str):
        raise ValueError(f"text must be a string, got {type(text).__name__}")
    if not 1 <= len(text) <= 2000:
        raise ValueError("text must be between 1 and 2000 characters")

    body = {"children": [{
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }]}
    base = os.environ.get("API_BASE_URL", "https://api.notion.com")
    headers = {"Notion-Version": "2022-06-28"}
    if token := os.environ.get("NOTION_TOKEN", ""):
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(base_url=base, timeout=20.0, headers=headers) as client:
        response = client.patch(f"/v1/blocks/{page_id}/children", json=body)
        response.raise_for_status()
    return f"appended a note to Notion page {page_id}"


tool = Tool.from_function(append_note, name="append_note", description="Append an update to a Notion page.")
tool.parameters = NOTE_SCHEMA
mcp.add_tool(tool)


if __name__ == "__main__":
    mcp.run()
