# Tempered

**Most MCP servers return success on malformed input, so agents fail silently.
This one builds them *and* proves they work before shipping.**

Tempered generates an MCP server from an OpenAPI spec, fires adversarial payloads
at every tool it exposes, repairs what fails, and publishes a grade.

*Tempering: heat it, test it, harden it — a tool is not finished until it has been proven.*

---

## The problem

An MCP server declares a JSON Schema for each tool. Nothing makes it *enforce*
that schema. Wrap an API in a try/except, return the friendliest string you can
think of, and you get a server that answers every call with success:

```
sent {"amount": 100001, "currency": "__not_in_enum__"}
got  charged 100001 __not_in_enum__ to user@example.com
```

The schema said `maximum: 100000` and `enum: [usd, eur, gbp]`. The agent believes
the charge went through. Nothing reaches error monitoring. That failure mode is
what Tempered calls **silent success**, and it is invisible to every existing tool.

## Quick start

```bash
python -m venv .venv && .venv/Scripts/pip install mcp fastmcp anthropic
```

### Web UI

```bash
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000>. Paste a spec URL to generate a server, then scan it
and watch findings stream in live as each adversarial payload lands. The repair
button runs the patch loop and renders the diff of every attempt.

Binds to localhost only, and deliberately: scanning a server means spawning the
process that runs it, so this endpoint executes commands. Local dev tool, not
something to expose.

### CLI

Scan a server you already have:

```bash
python -m tempered.cli test python path/to/server.py --fail-under B
```

Generate one from a spec, then scan it:

```bash
python -m tempered.cli generate https://petstore3.swagger.io/api/v3/openapi.json --out generated
python -m tempered.cli test python generated/petstore_server.py --html report.html
```

Repair what fails (needs `ANTHROPIC_API_KEY`):

```bash
python -m tempered.cli repair path/to/server.py --show-diff
```

Exit code is nonzero below `--fail-under`, so it works as a CI gate.

## See it work

```bash
python test_tempered.py
```

```
  good_server      A 100% over 20 checks
  broken_server    F 5%, 18 silent successes caught
  control          identical 20-check contract, opposite verdicts
  write safety     POST skipped by default, scanned with --allow-writes
```

Both fixtures declare the **identical schema**. One enforces it, one does not.
Every difference in verdict comes from enforcement alone — which is the whole
product in one line.

## How it works

```
OpenAPI spec
    |
    v
generate  ---> MCP server            (FastMCP does this part; it is commodity)
    |
    v
synth     ---> adversarial payloads  (one violated constraint each)
    |
    v
scan      ---> call every tool, classify every response
    |
    +-- clean --> report (grade + pass rate)
    |
    v
repair    ---> patch, re-run the FULL suite, max 2 attempts
```

### Schema-directed payload synthesis

For each tool's declared schema, Tempered walks every constraint and emits a
payload that violates **exactly one** of them, leaving everything else valid.

| Constraint | Violation sent |
|---|---|
| `type` | wrong primitive, `null` |
| `required` | field omitted |
| `enum` | value outside the set |
| `minimum` / `maximum` | out of bounds by one |
| `minLength` / `maxLength` | empty / oversized |
| `format` | malformed email, uri, date-time |
| `additionalProperties: false` | unexpected key |
| `items` | wrong-typed array element |

One violation per payload is load-bearing. Two violations make a failure
unattributable, and unattributable failures cannot be repaired automatically.

### The oracle

| Server response to an invalid payload | Verdict |
|---|---|
| JSON-RPC error, or `isError: true` | **PASS** — rejected it, correctly |
| Normal success result | **SILENT SUCCESS** — the headline finding |
| Timeout or crash | **CRASH** |
| Coerced and handled sanely | **AMBIGUOUS** — reported, not scored |

Grades band the pass rate: A ≥ 95%, B ≥ 85%, C ≥ 70%, D ≥ 50%, else F.

## Not lying to you

A conformance checker that flags correct servers is worse than no checker, so:

- **A known-good control ships with the repo.** `fixtures/good_server.py` must
  come back clean. The self-check fails if it ever does not.
- **Ambiguity is its own verdict.** Where the MCP spec does not clearly forbid a
  behaviour — coercing `"5"` to `5`, ignoring unknown keys — it is reported and
  excluded from the score rather than counted against the server.
- **Untestable is not the same as passing.** A tool that rejects its own valid
  example is marked `INCONCLUSIVE` and excluded from the grade. Without this, a
  server that is simply unreachable scores 100% for rejecting everything.
- **Writes are not fired at by default.** MCP carries no signal for whether a
  tool mutates state, so `generate` records the HTTP method beside the server and
  `test` skips anything that is not `GET`/`HEAD` unless you pass `--allow-writes`.

## Layout

```
tempered/
  synth.py      schema-directed payload synthesis   <- the core
  client.py     MCP protocol client (stdio)
  scan.py       the oracle: run, classify, grade
  repair.py     bounded patch loop, full re-verify
  generate.py   OpenAPI -> server, + method manifest
  report.py     terminal / HTML / JSON
  web.py        local UI, SSE-streamed scans
  static/       the one page it serves
  cli.py        test | repair | generate | serve
fixtures/
  schema.py         the contract both fixtures declare
  good_server.py    enforces it  -> must score A
  broken_server.py  ignores it   -> must score F
test_tempered.py    end-to-end self-check
```

## Status

Built at a hackathon. `test`, `generate`, `serve`, and the scan engine are
verified end-to-end against both fixtures and a live third-party API, through the
CLI and through the browser. The `repair` loop's
model call is **not yet live-tested** — it was written against the current
Anthropic SDK but no API key was available in the build environment.

Known limits: OpenAPI only (GraphQL and recorded traffic are the obvious next
ingest paths), single-call tools only (no create-then-read sequences), and no
handling for OAuth flows, pagination, or file uploads.
