"""Tempered CLI.

    tempered test <command> [args...]     scan a running MCP server
    tempered generate <spec> --out DIR    build an MCP server from an OpenAPI spec

Exits nonzero when the grade falls below --fail-under, so it works as a CI gate.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import report as report_mod
from .scan import grade_for, meets, scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tempered", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    test = sub.add_parser("test", help="scan an MCP server for conformance")
    test.add_argument("cmd", help="command that starts the server, e.g. python")
    test.add_argument("args", nargs="*", help="arguments to that command")
    test.add_argument("--name", help="label for the report (default: derived)")
    test.add_argument("--fail-under", default="F", metavar="GRADE",
                      help="exit nonzero below this grade (A-F, default F)")
    test.add_argument("--html", metavar="PATH", help="write an HTML report")
    test.add_argument("--json", metavar="PATH", help="write a JSON report")
    test.add_argument("--allow-writes", action="store_true",
                      help="also send adversarial payloads to non-GET tools")
    test.add_argument("-v", "--verbose", action="store_true", help="show passing checks too")

    fix = sub.add_parser("repair", help="scan a server, patch what fails, re-verify")
    fix.add_argument("source", help="path to the server's source file")
    fix.add_argument("--cmd", default=sys.executable, help="interpreter to run it with")
    fix.add_argument("--name", help="label for the report")
    fix.add_argument("--show-diff", action="store_true", help="print the patch for each attempt")

    web = sub.add_parser("serve", help="local web UI")
    web.add_argument("--port", type=int, default=8000)

    gen = sub.add_parser("generate", help="build an MCP server from an OpenAPI spec")
    gen.add_argument("spec", help="path or URL to an OpenAPI document")
    gen.add_argument("--out", required=True, metavar="DIR", help="where to write the server")
    gen.add_argument("--base-url", help="override the API base URL from the spec")
    gen.add_argument("--name", help="server name")

    opts = parser.parse_args(argv)
    if opts.command == "test":
        return _test(opts)
    if opts.command == "repair":
        return _repair(opts)
    if opts.command == "serve":
        from .web import serve

        serve(opts.port)
        return 0
    return _generate(opts)


def _repair(opts: argparse.Namespace) -> int:
    from .repair import MissingCredentials, repair, summary

    source = Path(opts.source)
    label = opts.name or source.stem
    try:
        result = asyncio.run(repair(source, opts.cmd, [str(source)], label))
    except MissingCredentials as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2

    if opts.show_diff:
        for attempt in result.attempts:
            print(f"\n--- attempt {attempt.number} "
                  f"({'kept' if attempt.kept else 'rejected'}) ---")
            print(attempt.diff)

    print(summary(result))
    return 0 if result.fixed else 1


def _test(opts: argparse.Namespace) -> int:
    from .generate import load_methods

    label = opts.name or " ".join([Path(opts.cmd).name, *opts.args])
    methods: dict[str, str] = {}
    for arg in opts.args:
        if arg.endswith(".py"):
            methods = load_methods(Path(arg))
            break
    result = asyncio.run(
        scan(opts.cmd, opts.args, label, methods=methods, allow_writes=opts.allow_writes)
    )

    print(report_mod.terminal(result, verbose=opts.verbose))

    if opts.html:
        _write(Path(opts.html), report_mod.to_html(result))
        print(f"  html  {opts.html}")
    if opts.json:
        _write(Path(opts.json), report_mod.to_json(result))
        print(f"  json  {opts.json}")

    if not result.gradable:
        print("  FAIL  nothing could be graded\n", file=sys.stderr)
        return 1

    threshold = opts.fail_under.upper()
    if not meets(result.grade, threshold):
        print(f"  FAIL  grade {result.grade} is below {threshold}\n", file=sys.stderr)
        return 1
    return 0


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generate(opts: argparse.Namespace) -> int:
    from .generate import generate

    path = generate(opts.spec, Path(opts.out), base_url=opts.base_url, name=opts.name)
    print(f"  wrote {path}")
    print(f"  test it:  tempered test python {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
