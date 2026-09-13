"""Local web UI for Tempered.

Binds to 127.0.0.1 only, and deliberately so: scanning a server means spawning
the process that runs it, so this endpoint executes commands. It is a local dev
tool, not something to put on a network.

Starlette + uvicorn + SSE all arrive with FastMCP, so this adds no dependencies.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator

from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from .generate import generate, load_methods
from .scan import scan

STATIC = Path(__file__).parent / "static"

# Keys the chat + generated servers use. Held in this process's environment only;
# never written to disk, never returned to the browser.
CHAT_KEYS = (
    "ANTHROPIC_API_KEY",       # chat, describe, repair
    "SLACK_WEBHOOK_URL",       # generated Slack tools
    "GITHUB_TOKEN",            # generated GitHub tools
    "OPENAI_API_KEY",          # generated OpenAI tools
    "API_TOKEN",               # generic bearer for OpenAPI-derived servers
)

CHAT_MODEL = "claude-sonnet-4-6"
CHAT_MAX_TURNS = 12  # ponytail: hard cap, bump if a real task needs longer chains


async def _pump(run: Any) -> AsyncIterator[dict[str, Any]]:
    """Run an async job that emits events into a queue, yielding them as they land."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def guarded(emit: Any) -> None:
        try:
            await run(emit)
        except BaseException as exc:  # noqa: BLE001
            emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    task = asyncio.create_task(guarded(queue.put_nowait))

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.25)
            yield {"data": _dumps(event)}
        except (asyncio.TimeoutError, TimeoutError):
            if task.done():
                break

    while not queue.empty():
        yield {"data": _dumps(queue.get_nowait())}

    if not task.cancelled() and (error := task.exception()):
        yield {"data": _dumps({"type": "error", "message": f"{type(error).__name__}: {error}"})}


def _dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str)


def _load_dotenv() -> None:
    """Populate os.environ from ./.env if present. Stdlib only.

    Real environment always wins — .env is a fallback for keys the user did
    not export from their shell. Handles quoted values and inline comments.
    """
    path = Path(".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


async def index(request: Request) -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def demo(request: Request) -> FileResponse:
    return FileResponse(STATIC / "demo.html")


async def api_scan(request: Request) -> EventSourceResponse:
    source = request.query_params.get("source", "").strip()
    allow_writes = request.query_params.get("allow_writes") == "1"
    if not source:
        return JSONResponse({"error": "source is required"}, status_code=400)

    command, args = sys.executable, [source]
    methods = load_methods(Path(source)) if source.endswith(".py") else {}
    label = Path(source).stem

    async def run(emit: Any) -> None:
        await scan(command, args, label, methods=methods,
                   allow_writes=allow_writes, on_event=emit)

    return EventSourceResponse(_pump(run))


async def api_generate(request: Request) -> JSONResponse:
    body = await request.json()
    spec = (body.get("spec") or "").strip()
    if not spec:
        return JSONResponse({"error": "spec is required"}, status_code=400)

    try:
        path = await asyncio.to_thread(
            generate, spec, Path("generated"), body.get("base_url") or None, body.get("name") or None
        )
    except Exception as exc:  # noqa: BLE001 - surface the reason to the UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    methods = load_methods(path)
    return JSONResponse({
        "server": str(path),
        "tools": len(methods),
        "writes": sum(1 for m in methods.values() if m not in ("get", "head", "options")),
    })


async def api_repair(request: Request) -> EventSourceResponse:
    source = request.query_params.get("source", "").strip()
    if not source:
        return JSONResponse({"error": "source is required"}, status_code=400)

    from .repair import credentials_available

    if not credentials_available():
        async def refuse(emit: Any) -> None:
            emit({
                "type": "error",
                "message": "repair needs ANTHROPIC_API_KEY set — add it in Keys",
            })
        return EventSourceResponse(_pump(refuse))

    async def run(emit: Any) -> None:
        from .repair import repair

        emit({"type": "repair_start", "source": source})
        result = await repair(Path(source), sys.executable, [source], Path(source).stem, verbose=False)
        for attempt in result.attempts:
            emit({
                "type": "attempt",
                "number": attempt.number,
                "kept": attempt.kept,
                "diff": attempt.diff,
                "grade": attempt.report.grade,
                "pass_rate": attempt.report.pass_rate,
            })
        emit({
            "type": "repair_done",
            "before": {"grade": result.before.grade, "pass_rate": result.before.pass_rate},
            "after": {"grade": result.after.grade, "pass_rate": result.after.pass_rate},
            "fixed": result.fixed,
        })

    return EventSourceResponse(_pump(run))


# --- Keys ---------------------------------------------------------------------


def _key_status() -> dict[str, bool]:
    return {k: bool(os.environ.get(k, "").strip()) for k in CHAT_KEYS}


async def api_keys(request: Request) -> JSONResponse:
    if request.method == "POST":
        body = await request.json()
        for key in CHAT_KEYS:
            value = (body.get(key) or "").strip()
            if value:
                os.environ[key] = value
        return JSONResponse({"set": _key_status()})
    return JSONResponse({"set": _key_status()})


# --- Chat ---------------------------------------------------------------------


def _to_anthropic_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """MCP ToolInfo -> Anthropic tool spec. Both use JSON Schema; direct pass-through."""
    return [
        {"name": t.name, "description": t.description or t.name, "input_schema": t.input_schema or {"type": "object"}}
        for t in tools
    ]


async def _chat_loop(server_path: str, messages: list[dict[str, Any]], emit: Any) -> None:
    """Run one turn of chat: user message in `messages[-1]`, tool loop until done."""
    import anthropic

    from . import client as mcp_client

    if not os.environ.get("ANTHROPIC_API_KEY"):
        emit({"type": "error", "message": "ANTHROPIC_API_KEY not set — add it in Keys"})
        return

    api = anthropic.Anthropic()
    async with mcp_client.connect(sys.executable, [server_path]) as server:
        tool_infos = await server.tools()
        tools = _to_anthropic_tools(tool_infos)
        emit({"type": "tools_loaded", "count": len(tools), "names": [t["name"] for t in tools]})

        for _ in range(CHAT_MAX_TURNS):
            resp = await asyncio.to_thread(
                api.messages.create,
                model=CHAT_MODEL,
                max_tokens=4000,
                tools=tools,
                messages=messages,
            )
            # Serialize assistant blocks so we can echo them AND persist for the next turn.
            assistant_blocks: list[dict[str, Any]] = []
            tool_uses = []
            for block in resp.content:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                    emit({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_blocks.append({
                        "type": "tool_use", "id": block.id, "name": block.name, "input": block.input,
                    })
                    emit({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                    tool_uses.append(block)
            messages.append({"role": "assistant", "content": assistant_blocks})

            if not tool_uses:
                break

            tool_results = []
            for tu in tool_uses:
                out = await server.call(tu.name, tu.input or {})
                is_error = out.kind != mcp_client.OK
                emit({"type": "tool_result", "id": tu.id, "content": out.text, "is_error": is_error})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": out.text, "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        emit({"type": "done", "messages": messages})


async def api_chat(request: Request) -> Any:
    body = await request.json()
    server_path = (body.get("server") or "").strip()
    messages = body.get("messages") or []
    if not server_path:
        return JSONResponse({"error": "server is required"}, status_code=400)
    if not messages:
        return JSONResponse({"error": "messages is required"}, status_code=400)

    async def run(emit: Any) -> None:
        await _chat_loop(server_path, messages, emit)

    return EventSourceResponse(_pump(run))


# --- Describe -> generate MCP server from English -----------------------------

DESCRIBE_MODEL = "claude-opus-4-7"

DESCRIBE_SYSTEM = """You write Python MCP servers using the FastMCP library.

Given the user's description of an app, output a COMPLETE, RUNNABLE Python file.

Required shape:

    import os
    import httpx
    from fastmcp import FastMCP

    mcp = FastMCP("some-descriptive-name")

    @mcp.tool()
    async def tool_name(arg: str, another: int = 10) -> str:
        \"\"\"One-line description of what this tool does. This is what the calling
        model sees when deciding which tool to use.\"\"\"
        # Validate. Raise ValueError with a clear message when input violates any
        # constraint you documented (enum, range, format). No silent success.
        if not arg:
            raise ValueError("arg must not be empty")
        # Call the real API.
        token = os.environ.get("SOME_ENV_VAR")
        if not token:
            raise RuntimeError("SOME_ENV_VAR is not set")
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post("https://api.example.com/...", json={...},
                                  headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            return r.text

    if __name__ == "__main__":
        mcp.run()

Rules:
- Use real API endpoints you actually know. If the user names an API you don't
  know well, prefer fewer tools that are correct over many that are guessed.
- Read every secret from os.environ. Common ones already available:
  SLACK_WEBHOOK_URL, GITHUB_TOKEN, OPENAI_API_KEY. Use those names when they fit.
- Each tool: typed parameters, one-line docstring, input validation with clear
  ValueError messages, real HTTP call, meaningful return string.
- Do NOT invent endpoints or auth flows. If unsure, skip the tool.
- 1 to 6 tools per server. Keep tools focused; the calling model picks by name.

Return ONLY the Python file inside a single ```python code block. No commentary."""


def _extract_python(text: str) -> str | None:
    import re
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return blocks[-1].strip() + "\n" if blocks else None


def _slug(text: str, limit: int = 32) -> str:
    import hashlib
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:limit] or "app"
    tag = hashlib.sha1(text.encode()).hexdigest()[:6]
    return f"{slug}_{tag}"


def _describe_sync(description: str) -> str:
    """One Claude call. Returns generated Python source, or raises."""
    import anthropic
    api = anthropic.Anthropic()
    resp = api.messages.create(
        model=DESCRIBE_MODEL,
        max_tokens=8000,
        system=DESCRIBE_SYSTEM,
        messages=[{"role": "user", "content": description}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    code = _extract_python(text)
    if not code:
        raise RuntimeError("model returned no code block")
    return code


async def api_describe(request: Request) -> JSONResponse:
    body = await request.json()
    description = (body.get("description") or "").strip()
    if not description:
        return JSONResponse({"error": "description is required"}, status_code=400)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return JSONResponse({"error": "ANTHROPIC_API_KEY not set — add it in Keys"}, status_code=400)

    try:
        code = await asyncio.to_thread(_describe_sync, description)
    except Exception as exc:  # noqa: BLE001 - surface reason to UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    out_dir = Path("generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_slug(description)}.py"
    path.write_text(code, encoding="utf-8")

    # Count @mcp.tool occurrences as a rough tool count for the UI.
    tool_count = code.count("@mcp.tool")
    return JSONResponse({"server": str(path), "tools": tool_count, "description": description})


# --- Presets ------------------------------------------------------------------

# Curated apps with public OpenAPI specs. Only ones verified to actually load
# go here — a broken preset in the demo is worse than fewer presets.
PRESETS = [
    {
        "id": "petstore",
        "label": "Petstore (demo, no auth)",
        "spec": "https://petstore3.swagger.io/api/v3/openapi.json",
        "hint": "Try: 'find pets with status available' or 'add a new pet named Rex'",
    },
]


async def api_presets(request: Request) -> JSONResponse:
    return JSONResponse({"presets": PRESETS})


app = Starlette(routes=[
    Route("/", index),
    Route("/demo", demo),
    Route("/api/scan", api_scan),
    Route("/api/generate", api_generate, methods=["POST"]),
    Route("/api/repair", api_repair),
    Route("/api/keys", api_keys, methods=["GET", "POST"]),
    Route("/api/chat", api_chat, methods=["POST"]),
    Route("/api/describe", api_describe, methods=["POST"]),
    Route("/api/presets", api_presets),
])


def serve(port: int = 8000) -> None:
    import uvicorn

    _load_dotenv()
    loaded = [k for k in CHAT_KEYS if os.environ.get(k)]
    print(f"  tempered ui  ->  http://127.0.0.1:{port}")
    if loaded:
        print(f"  keys from env: {', '.join(loaded)}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
