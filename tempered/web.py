"""Local web UI for Tempered.

Binds to 127.0.0.1 only, and deliberately so: scanning a server means spawning
the process that runs it, so this endpoint executes commands. It is a local dev
tool, not something to put on a network.

Starlette + uvicorn + SSE all arrive with FastMCP, so this adds no dependencies.
"""

from __future__ import annotations

import asyncio
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


app = Starlette(routes=[
    Route("/", index),
    Route("/api/scan", api_scan),
    Route("/api/generate", api_generate, methods=["POST"]),
    Route("/api/repair", api_repair),
])


def serve(port: int = 8000) -> None:
    import uvicorn

    print(f"  tempered ui  ->  http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
