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


async def _pump(run: Any) -> AsyncIterator[dict[str, Any]]:
    """Run an async job that emits events into a queue, yielding them as they land."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def guarded(emit: Any) -> None:
        # BaseException too: a SystemExit from anything downstream would
        # otherwise unwind the event loop and take the whole server with it.
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

    while not queue.empty():  # drain anything emitted after the last poll
        yield {"data": _dumps(queue.get_nowait())}

    if not task.cancelled() and (error := task.exception()):
        yield {"data": _dumps({"type": "error", "message": f"{type(error).__name__}: {error}"})}


def _dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str)


async def index(request: Request) -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def api_scan(request: Request) -> EventSourceResponse:
    """SSE: stream every finding as the scan makes it."""
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
    """SSE: scan, patch, re-verify. Emits the diff of every attempt."""
    source = request.query_params.get("source", "").strip()
    if not source:
        return JSONResponse({"error": "source is required"}, status_code=400)

    from .repair import credentials_available

    if not credentials_available():
        # EventSource cannot read a 400 body, so send the reason down the stream
        # where the page can actually show it.
        async def refuse(emit: Any) -> None:
            emit({
                "type": "error",
                "message": "repair needs ANTHROPIC_API_KEY set before you start the server",
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


# --- Presence agent: draft -> confirm -> publish on Tempered connectors --------

# BYO keys the presence agent uses. Held in this process's environment only
# (never written to disk, never returned to the browser) — fine for a localhost
# dev tool, which is the only thing this server is meant to be.
PRESENCE_KEYS = (
    "ANTHROPIC_API_KEY", "DISCORD_WEBHOOK_URL", "SLACK_WEBHOOK_URL",
    "GITHUB_TOKEN", "GITHUB_REPO", "NOTION_TOKEN", "NOTION_PAGE_ID",
)


def _key_status() -> dict[str, bool]:
    return {k: bool(os.environ.get(k, "").strip()) for k in PRESENCE_KEYS}


async def api_presence_keys(request: Request) -> JSONResponse:
    """GET reports which keys are set (booleans only). POST stores provided keys."""
    if request.method == "POST":
        body = await request.json()
        for key in PRESENCE_KEYS:
            value = (body.get(key) or "").strip()
            if value:
                os.environ[key] = value
        return JSONResponse({"set": _key_status()})
    return JSONResponse({"set": _key_status()})


async def api_presence_plan(request: Request) -> JSONResponse:
    """Draft tailored posts. Executes nothing — returns proposals to confirm."""
    from presence.agent import CONNECTORS, plan

    body = await request.json()
    whats_new = (body.get("whats_new") or "").strip()
    platforms = [str(p) for p in (body.get("platforms") or [])]
    if not whats_new:
        return JSONResponse({"error": "Tell me what's new first."}, status_code=400)
    if not platforms:
        return JSONResponse({"error": "Pick at least one platform."}, status_code=400)
    try:
        proposals, notes = await plan(whats_new, platforms)
    except Exception as exc:  # noqa: BLE001 - surface the reason to the UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=400)

    def serialize(p: Any) -> dict[str, Any]:
        return {
            "platform": p.platform, "label": p.label,
            "fields": [
                {"name": f.name, "label": f.label, "limit": f.limit, "value": p.values.get(f.name, "")}
                for f in CONNECTORS[p.platform].fields
            ],
        }

    return JSONResponse({"notes": notes, "proposals": [serialize(p) for p in proposals]})


_sink_url: str | None = None


def _sink() -> str:
    """A local catch-all that 200s any request. Proving a connector fires
    adversarial payloads at IT, never the real API — so writes are safe."""
    global _sink_url
    if _sink_url:
        return _sink_url
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _ok(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _ok  # type: ignore[assignment]

        def log_message(self, *a: Any) -> None:
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _sink_url = f"http://127.0.0.1:{srv.server_address[1]}"
    return _sink_url


async def api_presence_prove(request: Request) -> Any:
    """SSE: run the conformance scan on a connector, pointed at the safe sink.

    This is the 'Tempered proves it' beat — the same adversarial suite that grades
    any MCP server, run against the connectors the agent will actually use.
    """
    from presence.agent import CONNECTORS

    from .generate import load_methods

    platform = request.query_params.get("platform", "").strip()
    connector = CONNECTORS.get(platform)
    if not connector:
        return JSONResponse({"error": f"no connector for {platform!r}"}, status_code=400)

    server_path = connector.server
    methods = load_methods(Path(server_path))
    env = {**os.environ, "API_BASE_URL": _sink()}  # adversarial writes hit the sink, not the API

    async def run(emit: Any) -> None:
        await scan(sys.executable, [server_path], f"{connector.label} connector",
                   methods=methods, allow_writes=True, on_event=emit, env=env)

    return EventSourceResponse(_pump(run))


async def api_presence_repair(request: Request) -> Any:
    """SSE: harden a connector — the repair loop, pointed at the safe sink.

    Rewrites the connector in place to enforce its declared schema. The scans
    inside fire at the sink (allow_writes is safe for that reason), so nothing
    reaches the real API. This is the 'generate -> prove -> harden' close.
    """
    from presence.agent import CONNECTORS

    from .generate import load_methods
    from .repair import credentials_available, repair

    platform = request.query_params.get("platform", "").strip()
    connector = CONNECTORS.get(platform)
    if not connector:
        return JSONResponse({"error": f"no connector for {platform!r}"}, status_code=400)

    if not credentials_available():
        async def refuse(emit: Any) -> None:
            emit({"type": "error", "message": "repair needs ANTHROPIC_API_KEY set before you start the server"})
        return EventSourceResponse(_pump(refuse))

    server_path = Path(connector.server)
    methods = load_methods(server_path)
    env = {**os.environ, "API_BASE_URL": _sink()}

    async def run(emit: Any) -> None:
        emit({"type": "repair_start", "source": str(server_path)})
        result = await repair(server_path, sys.executable, [str(server_path)],
                              f"{connector.label} connector", verbose=False,
                              allow_writes=True, methods=methods, env=env)
        for attempt in result.attempts:
            emit({"type": "attempt", "number": attempt.number, "kept": attempt.kept,
                  "diff": attempt.diff, "grade": attempt.report.grade,
                  "pass_rate": attempt.report.pass_rate})
        emit({"type": "repair_done",
              "before": {"grade": result.before.grade, "pass_rate": result.before.pass_rate},
              "after": {"grade": result.after.grade, "pass_rate": result.after.pass_rate},
              "fixed": result.fixed})

    return EventSourceResponse(_pump(run))


async def api_presence_publish(request: Request) -> JSONResponse:
    """Publish only the (possibly edited) proposals the user approved."""
    from presence.agent import Proposal, publish

    body = await request.json()
    proposals = [
        Proposal(platform=i["platform"], values={k: str(v) for k, v in (i.get("values") or {}).items()})
        for i in (body.get("proposals") or [])
        if any(str(v).strip() for v in (i.get("values") or {}).values())
    ]
    if not proposals:
        return JSONResponse({"error": "Nothing to publish."}, status_code=400)
    results = await publish(proposals)
    return JSONResponse({"results": [
        {"platform": r.platform, "label": r.label, "ok": r.ok, "detail": r.detail} for r in results
    ]})


app = Starlette(routes=[
    Route("/", index),
    Route("/api/scan", api_scan),
    Route("/api/generate", api_generate, methods=["POST"]),
    Route("/api/repair", api_repair),
    Route("/api/presence/keys", api_presence_keys, methods=["GET", "POST"]),
    Route("/api/presence/plan", api_presence_plan, methods=["POST"]),
    Route("/api/presence/publish", api_presence_publish, methods=["POST"]),
    Route("/api/presence/prove", api_presence_prove),
    Route("/api/presence/repair", api_presence_repair),
])


def serve(port: int = 8000) -> None:
    import uvicorn

    print(f"  tempered ui  ->  http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
