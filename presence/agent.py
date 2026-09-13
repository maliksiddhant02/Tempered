"""The presence agent: draft -> confirm -> publish, across Tempered connectors.

Two functions, split on purpose:

- `plan()` runs the model with the connectors' publish tools available, but
  EXECUTES NOTHING. Every tool the model calls is intercepted and recorded as a
  Proposal. This is the multi-step part: the model tailors one post per platform.
- `publish()` runs only the proposals a human approved, calling the real MCP
  connector (which makes the real HTTP request).

The gap between them is the confirmation gate the user asked for: nothing leaves
the machine until someone says yes. Secrets (webhook tokens, API keys) are
injected here from the environment (BYO keys) and are never shown to the model.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tempered.client import OK, connect
from tempered.repair import MissingCredentials, credentials_available  # reuse the key check

MODEL = "claude-opus-5"
ROOT = Path(__file__).parent

SYSTEM = """You help a professional keep their public presence up to date.

The user tells you what is new — a shipped project, a talk, an award, a new role.
For EACH target platform, write one update tailored to that platform and call
that platform's post tool with the finished text in every field it asks for.
Tailor tone and length: a dev community (Discord/Slack) is warmer and shorter;
GitHub and a profile page are more formal.

Hard rules:
- Use ONLY facts the user gave you. Never invent metrics, dates, names, links,
  or outcomes. If something is unclear, write the honest, smaller version.
- One post per requested platform. Call each tool exactly once.
- After you have called the tool for every requested platform, stop.
"""


@dataclass(frozen=True)
class Field:
    name: str            # the argument name on the connector's tool
    label: str           # human label for the UI
    limit: int           # max characters, surfaced to the model and enforced


@dataclass(frozen=True)
class Connector:
    platform: str
    label: str
    server: str                       # generated MCP server that does the real request
    tool: str                         # the MCP tool name inside it
    fields: tuple[Field, ...]         # the parts the MODEL drafts
    style: str                        # tone guidance for the model
    secrets: Callable[[], dict[str, Any]]   # BYO creds -> extra tool args (raises if missing)
    env: Callable[[], dict[str, str]] = field(default=lambda: {})  # extra process env


def _need(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value:
        raise MissingCredentials(f"{var} is not set — add it before publishing")
    return value


def _discord_secrets() -> dict[str, Any]:
    # https://discord.com/api/webhooks/<id>/<token>
    url = _need("DISCORD_WEBHOOK_URL")
    m = re.search(r"/webhooks/([^/]+)/([^/?#]+)", url)
    if not m:
        raise MissingCredentials("DISCORD_WEBHOOK_URL does not look like a webhook URL")
    return {"webhook_id": m.group(1), "webhook_token": m.group(2)}


def _slack_secrets() -> dict[str, Any]:
    # https://hooks.slack.com/services/T.../B.../xxxx
    url = _need("SLACK_WEBHOOK_URL")
    m = re.search(r"/services/([^/]+)/([^/]+)/([^/?#]+)", url)
    if not m:
        raise MissingCredentials("SLACK_WEBHOOK_URL does not look like a webhook URL")
    return {"t1": m.group(1), "t2": m.group(2), "t3": m.group(3)}


def _github_secrets() -> dict[str, Any]:
    repo = _need("GITHUB_REPO")  # "owner/name"
    if "/" not in repo:
        raise MissingCredentials("GITHUB_REPO must look like owner/name")
    owner, name = repo.split("/", 1)
    return {"owner": owner, "repo": name}


def _github_env() -> dict[str, str]:
    return {
        "API_TOKEN": _need("GITHUB_TOKEN"),
        "API_HEADERS": json.dumps({"Accept": "application/vnd.github+json"}),
    }


CONNECTORS: dict[str, Connector] = {
    "discord": Connector(
        platform="discord", label="Discord",
        server=str(ROOT / "connectors" / "discord_server.py"),
        tool="post_update", fields=(Field("content", "Message", 2000),),
        style="Warm, concise, first person. An emoji or two is fine. No hashtag spam.",
        secrets=_discord_secrets,
    ),
    "slack": Connector(
        platform="slack", label="Slack",
        server=str(ROOT / "connectors" / "slack_server.py"),
        tool="post_update", fields=(Field("text", "Message", 3000),),
        style="Team-channel tone: friendly and concise, first person.",
        secrets=_slack_secrets,
    ),
    "github": Connector(
        platform="github", label="GitHub",
        server=str(ROOT / "connectors" / "github_server.py"),
        tool="create_issue",
        fields=(Field("title", "Issue title", 120), Field("body", "Issue body", 4000)),
        style="Formal changelog/announcement tone. Markdown is welcome in the body.",
        secrets=_github_secrets, env=_github_env,
    ),
}


@dataclass
class Proposal:
    platform: str
    values: dict[str, str]           # field name -> drafted text
    tool_use_id: str = ""

    @property
    def label(self) -> str:
        return CONNECTORS[self.platform].label


@dataclass
class Result:
    platform: str
    ok: bool
    detail: str

    @property
    def label(self) -> str:
        return CONNECTORS[self.platform].label


def _anthropic_tool(c: Connector) -> dict[str, Any]:
    props = {
        f.name: {"type": "string", "description": f"{f.label} (max {f.limit} characters)."}
        for f in c.fields
    }
    return {
        "name": f"post_to_{c.platform}",
        "description": f"Publish the update to {c.label}. {c.style}",
        "input_schema": {"type": "object", "required": [f.name for f in c.fields], "properties": props},
    }


def _unknown(platforms: list[str]) -> list[str]:
    return [p for p in platforms if p not in CONNECTORS]


async def plan(whats_new: str, platforms: list[str]) -> tuple[list[Proposal], str]:
    """Draft a tailored post per platform. Executes nothing; returns proposals.

    The model may call each platform's post tool; we intercept the call, record
    the drafted fields, and answer with a synthetic 'queued' result so it moves on.
    """
    if not credentials_available():
        raise MissingCredentials("the agent needs ANTHROPIC_API_KEY set")
    if unknown := _unknown(platforms):
        raise ValueError(f"no connector for: {', '.join(unknown)}")

    import anthropic

    client = anthropic.Anthropic()
    tools = [_anthropic_tool(CONNECTORS[p]) for p in platforms]
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": f"What's new:\n\n{whats_new}\n\nTarget platforms: {', '.join(platforms)}."}
    ]

    proposals: list[Proposal] = []
    seen: set[str] = set()
    notes = ""

    for _ in range(len(platforms) + 2):  # bounded: one turn per platform, plus slack
        resp = await asyncio.to_thread(
            client.messages.create,
            model=MODEL, max_tokens=4000, system=SYSTEM, tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})
        notes = "".join(b.text for b in resp.content if b.type == "text").strip() or notes

        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            break

        results = []
        for call in calls:
            platform = call.name.removeprefix("post_to_")
            conn = CONNECTORS.get(platform)
            if conn and platform not in seen:
                data = call.input or {}
                values = {f.name: str(data.get(f.name, "")).strip()[: f.limit] for f in conn.fields}
                if any(values.values()):
                    proposals.append(Proposal(platform, values, call.id))
                    seen.add(platform)
            results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": "Draft queued for the user to confirm. Do not call this tool again.",
            })
        messages.append({"role": "user", "content": results})

    return proposals, notes


async def publish(proposals: list[Proposal]) -> list[Result]:
    """Execute approved proposals for real, injecting BYO secrets per platform."""
    results: list[Result] = []
    for p in proposals:
        c = CONNECTORS[p.platform]
        try:
            args = {**c.secrets(), **p.values}
            env = {**os.environ, **c.env()}
        except MissingCredentials as exc:
            results.append(Result(p.platform, False, str(exc)))
            continue
        try:
            async with connect(sys.executable, [c.server], env=env) as server:
                out = await server.call(c.tool, args)
            results.append(Result(p.platform, out.kind == OK, out.text))
        except Exception as exc:  # noqa: BLE001 - report, never crash the caller
            results.append(Result(p.platform, False, f"{type(exc).__name__}: {exc}"))
    return results


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    # Windows consoles default to cp1252 and choke on emoji in drafts.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - older streams lack reconfigure; fine
            pass

    ap = argparse.ArgumentParser(prog="presence", description="draft -> confirm -> publish")
    ap.add_argument("whats_new", help="what is new (the agent drafts from this)")
    ap.add_argument("--to", required=True, help="comma-separated platforms, e.g. discord,slack")
    ap.add_argument("--yes", action="store_true", help="publish without the interactive gate")
    opts = ap.parse_args(argv)
    platforms = [p.strip() for p in opts.to.split(",") if p.strip()]

    try:
        proposals, notes = asyncio.run(plan(opts.whats_new, platforms))
    except (MissingCredentials, ValueError) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2

    if notes:
        print(f"\n  agent: {notes}\n")
    if not proposals:
        print("  no drafts produced")
        return 1
    for p in proposals:
        print(f"  --- {p.label} ---")
        for name, text in p.values.items():
            print(f"  [{name}] {text}")
        print()

    if not opts.yes:
        reply = input("  publish these? [y/N] ").strip().lower()
        if reply != "y":
            print("  held — nothing posted")
            return 0

    for r in asyncio.run(publish(proposals)):
        print(f"  {r.label}: {'posted' if r.ok else 'FAILED — ' + r.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
