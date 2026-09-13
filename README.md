# Tempered

**A multi-step agent that keeps your professional presence current across your
apps — over connectors it *proves* before it trusts them.**

Tempered generates an MCP connector for an app from its API spec, fires an
adversarial conformance suite at it, repairs what fails, and only then lets the
agent use it. The agent drafts an update tailored to each platform, waits for
your confirmation, and publishes — to Discord, Slack, GitHub and Notion.

*Tempering: heat it, test it, harden it — a tool is not finished until it has been proven.*

---

## The brief, answered

| Requirement | How |
|---|---|
| One useful, multi-step AI agent | The presence agent: draft a tailored post per platform → confirm → publish → (help reply). A real tool-use loop over MCP connectors. |
| Connect to ≥ 3 external apps | **Discord, Slack, GitHub, Notion** — all reached through generated MCP connectors, BYO keys. |
| Show how you know it works | Tempered's conformance engine grades every connector, and repairs the ones that fail. Proof, not screenshots. |

## Quick start

```bash
python -m venv .venv && .venv/Scripts/pip install mcp fastmcp anthropic
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000>:

1. **Connections & keys** — paste your Anthropic key and a **Discord webhook URL**
   (Server Settings → Integrations → Webhooks → New; ~30 seconds). Keys are held
   in memory, localhost only, never returned to the browser.
2. **What's new** — type it, pick platforms, **Draft**. The agent writes one post
   per platform, tailored, using only facts you gave it.
3. Edit if you like, then **Publish approved**. Nothing is sent until you click.
4. **Prove** any connector to see its conformance grade; **Harden** a failing one
   to watch Tempered rewrite it to enforce its schema, then re-prove.

Binds to localhost only, deliberately: scanning a connector spawns the process
that runs it, so this endpoint executes commands. Local tool, not for a network.

## The two halves

### The agent — `presence/`

`plan()` runs the model with the connectors' publish tools available but
**executes nothing**: every call is intercepted and recorded as a proposal (this
is the multi-step, per-platform drafting). `publish()` runs only the proposals
you approved, injecting BYO secrets the model never sees. The gap between them is
the confirmation gate.

For closed platforms with no write API (LinkedIn, Seek, Prosple), the honest move
is the same shape without the last step: draft it, hand you the text.

### The engine — `tempered/`

```
API spec ──generate──▶ MCP connector ──prove──▶ grade
                                          │
                                          └─ F? ──repair──▶ enforce schema ──▶ A
```

An MCP server declares a JSON Schema for each tool. Nothing makes it *enforce*
that schema. Wrap an API, return the friendliest string you can, and you get a
server that answers every call with success:

```
sent {"content": 100001-char-string}   (declared maxLength: 2000)
got  success
```

The agent believes it worked. Nothing reaches error monitoring. Tempered calls
that **silent success**, and it is invisible to every existing tool.

**Schema-directed synthesis.** For each tool's schema, Tempered walks every
constraint and emits a payload that violates **exactly one** — wrong type, out of
enum, missing required, out of bounds, bad format, extra key. One violation per
payload is load-bearing: two would make a failure unattributable, and
unattributable failures cannot be repaired automatically.

**The oracle.** JSON-RPC error / `isError` → **PASS** (rejected, correctly). A
normal success result → **SILENT SUCCESS** (the headline). Timeout/crash →
**CRASH**. Coerced sanely → **AMBIGUOUS** (reported, not scored). Grades band the
pass rate: A ≥ 95%, B ≥ 85%, C ≥ 70%, D ≥ 50%, else F.

### What proving the connectors found

FastMCP's `from_openapi` generates connectors that **do not enforce their declared
schemas** — they forward an integer where a string was declared, a message past
its length limit, a missing required field, all returning success. So the Discord,
Slack and GitHub connectors score **F** out of the box. The hand-written Notion
connector, which validates, scores **A** — the positive control. Tempered isn't
flagging everything; it tells you which connectors you can actually trust, and
`repair` rewrites a failing one into explicit tools that validate first, then make
the same request. Verified **F → A** in one attempt, with the hardened connector
still publishing valid input.

## Not lying to you

A conformance checker that flags correct servers is worse than none, so:

- **A known-good control ships with the repo.** `fixtures/good_server.py` must come
  back clean; the self-check fails if it ever does not. Notion is the same idea
  among the real connectors.
- **Ambiguity is its own verdict**, excluded from the score.
- **Untestable ≠ passing.** A tool that rejects its own valid example is
  `INCONCLUSIVE`; a reachable tool with nothing to violate contributes no grade —
  no vacuous A.
- **Writes are not fired at by default.** `generate` records each tool's HTTP
  method; the scanner skips non-GET tools unless you pass `--allow-writes`. Proving
  a connector points it at a local sink first, so adversarial writes never reach
  the real API.

## See it work

```bash
python test_tempered.py
```

```
  good_server      A 100% over 20 checks
  broken_server    F 5%, 18 silent successes caught
  control          identical 20-check contract, opposite verdicts
  write safety     POST skipped by default, scanned with --allow-writes
  presence         webhook parsing + connector registry
```

CLI, for the engine on its own:

```bash
python -m tempered.cli generate https://petstore3.swagger.io/api/v3/openapi.json --out generated
python -m tempered.cli test python generated/<name>_server.py --html report.html
python -m tempered.cli repair path/to/server.py --show-diff   # needs ANTHROPIC_API_KEY
```

## Layout

```
presence/
  agent.py            plan() drafts, publish() sends; the confirmation gate between
  connectors/         generated (Discord/Slack/GitHub) + hand-written (Notion)
  specs/              the focused API specs the connectors are generated from
tempered/
  synth.py            schema-directed payload synthesis          ← the core
  scan.py             the oracle: run, classify, grade
  repair.py           bounded patch loop, full re-verify
  generate.py         OpenAPI → connector, + method manifest
  report.py           terminal / HTML / JSON
  web.py              local UI: draft/publish + prove/harden, SSE-streamed
  static/             the one page it serves
  cli.py              test | repair | generate | serve
fixtures/             good (A) and broken (F) — identical contract, opposite verdicts
test_tempered.py      end-to-end self-check
DEMO.md               the 2-minute run-through
```

## Status

Built at a hackathon. The agent (draft → confirm → publish to Discord/Slack/GitHub/
Notion), the engine (generate/prove/repair), and the web UI are verified end to
end. `repair` is proven live, including hardening a generated connector **F → A**.
The connectors ship at F on purpose — the demo hardens them live; `git checkout
presence/connectors` resets them.

Known limits: single-call tools (no create-then-read sequences); OpenAPI in, so
GraphQL and closed platforms (LinkedIn/Seek/Prosple) are draft-and-hand-off, not
auto-publish; no OAuth flows.
