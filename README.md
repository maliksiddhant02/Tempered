# Tempered

A multi-step agent that keeps your work presence up to date across the apps you
use, running on connectors it tests before it trusts them.

The name comes from metalworking: you stress a blade to find where it gives before
you rely on it. Same rule here for a connector.

---

## 01 · Project overview

Keeping up to date across a community Discord, a team Slack, GitHub, and a Notion
page is a small recurring chore, and wiring an agent to each app usually means
trusting connectors nobody checked.

Tempered is two parts. The agent (`presence/`) takes "here's what's new", writes a
post for each platform, waits for you to confirm, and publishes. It only uses the
facts you gave it. The engine (`tempered/`) builds an MCP connector for an app from
its API spec, throws malformed input at it, grades how it responds, and repairs it
if it fails. The agent is only allowed to use connectors that have passed.

The real problem sits underneath both. An MCP server declares a JSON Schema for
each tool, but nothing forces it to obey that schema. A connector can take garbage
input and still answer with success, so the agent acts on the garbage and nothing
turns up in error monitoring. We call that a silent success, and catching it is the
whole reason the engine exists. The idea we started from was "teach someone to
fish": the agent can reach any app, because Tempered can build and test the
connector for it.

## 02 · External apps used

The agent talks to four apps. We chose ones with simple key or webhook auth so
there was no OAuth detour to burn the day on.

| App | Connector | What it does |
|---|---|---|
| Discord | generated from an OpenAPI spec | posts an update through an incoming webhook |
| Slack | generated from an OpenAPI spec | posts an update through an incoming webhook |
| GitHub | generated from an OpenAPI spec | opens an issue (title and body) through the REST API |
| Notion | hand-written adapter | appends an update to a page |

All four go through the Model Context Protocol over stdio. Keys are yours: you
enter them in the UI and they stay in memory. For apps with no write API (LinkedIn,
Seek, Prosple), the agent drafts the text and hands it to you rather than
pretending it can post on your behalf.

## 03 · Setup instructions

```bash
python -m venv .venv
.venv/Scripts/pip install mcp fastmcp anthropic          # Windows; use .venv/bin/pip on macOS/Linux
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000> and:

1. Expand **Connections & keys** and paste your Anthropic API key and a Discord
   webhook URL (in Discord: Server Settings, Integrations, Webhooks, New Webhook,
   Copy URL). Add Slack, GitHub, or Notion keys the same way for those apps, then
   **Save keys**.
2. Type what's new, tick the platforms you want, and hit **Draft**.
3. Edit the drafts if you want, then **Publish approved**. It posts to your real
   channels, and nothing goes out until you click.
4. **Prove** any connector to see its conformance grade, or **Harden** a failing
   one to watch Tempered rewrite it and grade it again.

The server binds to `127.0.0.1` on purpose. Scanning a connector spawns the process
that runs it, so this endpoint executes commands. Run it locally; don't put it on a
network.

## 04 · Reliability testing

This is the part we spent the most time on. The engine's whole job is to check the
connectors, so "does it work" has an answer you can run rather than a claim you have
to take on faith.

The whole thing runs at once:

```bash
python test_tempered.py
```

```
  synth            10 violations, one mutation each
  grading          bands, thresholds, no vacuous A
  good_server      A 100% over 20 checks
  broken_server    F 5%, 18 silent successes caught
  control          identical 20-check contract, opposite verdicts
  write safety     POST skipped by default, scanned with --allow-writes
  presence         webhook parsing + connector registry
```

Here's how the check works. For each tool's schema, Tempered generates one payload
per constraint, and each payload breaks exactly one rule: a wrong type, a missing
required field, a value past a length or range limit, a key that shouldn't be
there. Keeping it to one break per payload matters, because if two things are wrong
at once you can't tell which one the server failed to catch, and you can't
auto-repair what you can't pin down. An oracle then sorts each reply. A proper
JSON-RPC error (or `isError`) counts as a pass. A plain success reply to bad input
is a silent success, which is the case we care about. A timeout or crash is a
crash, and a sensible type coercion is marked ambiguous and left out of the score.
The pass rate becomes a grade: A at 95% and up, then B, C, D, and F at the bottom.

When we ran this against the connectors, it caught something. FastMCP's
`from_openapi` connectors don't actually enforce their schemas; they forward
whatever they're handed, so an integer where a string was declared, or a message
well past its length limit, comes back as success. Discord, Slack, and GitHub all
score F. The Notion connector, which we wrote to validate its input, scores A. That
A/F split is the useful part: a connector that validates passes, and one that
doesn't fails, so the grade tells you which ones to trust.

The `repair` command rewrites a failing connector so it validates its input first
and then makes the same request. We watched it take a connector from F to A in a
single pass, and the rewritten connector still publishes valid posts, so the agent
keeps working through it. Repair is capped at two attempts, re-runs the full suite
after each patch, keeps a patch only if the score actually improved, and puts the
original back if a rewrite won't even run.

We also don't take the harness at its word, because a checker that flags correct
servers is worse than no checker:

- A known-good server ships in the repo (`fixtures/good_server.py`, and Notion
  among the real connectors). If the harness ever flags it, the self-check fails.
- Sensible coercions are marked ambiguous and don't count against a server.
- A tool that rejects its own valid example is marked inconclusive, and a reachable
  tool with nothing to violate earns no grade, so an unreachable server can't score
  a hollow A.
- Writes are handled carefully. `generate` records each tool's HTTP method, and the
  scanner skips anything that isn't a GET unless you pass `--allow-writes`. When it
  proves a connector it points that connector at a local sink first, so the
  adversarial writes never reach the real API.

## 05 · Demo video

▶ **[Add your ≤2-minute demo link here]**

The run it follows is written up in [DEMO.md](DEMO.md): the agent drafts and
publishes across platforms, then Prove Discord (F, full of silent successes), Prove
Notion (A), and Harden Discord (F to A).

---

## How it works

```
What's new ──▶ agent drafts per platform ──▶ you confirm ──▶ publish
                                                              │
each connector:  API spec ──generate──▶ MCP connector ──prove──▶ grade
                                                              └─ F? ──repair──▶ A
```

The agent's `plan()` runs the model with the connectors' publish tools available
but runs none of them. It intercepts each call and records it as a proposal, which
is where the per-platform drafting happens. `publish()` then runs only the
proposals you approved, filling in the BYO secrets that the model never sees. The
confirmation gate is that gap between the two.

## Layout

```
presence/
  agent.py            plan() drafts, publish() sends; the confirmation gate between
  connectors/         generated (Discord/Slack/GitHub) + hand-written (Notion)
  specs/              the focused API specs the connectors are generated from
tempered/
  synth.py            schema-directed payload synthesis          <- the core
  scan.py             the oracle: run, classify, grade
  repair.py           bounded patch loop, full re-verify
  generate.py         OpenAPI to connector, plus a method manifest
  report.py           terminal / HTML / JSON
  web.py              local UI: draft/publish plus prove/harden, streamed over SSE
  cli.py              test | repair | generate | serve
fixtures/             good (A) and broken (F): same contract, opposite verdicts
test_tempered.py      end-to-end self-check
DEMO.md               the 2-minute run-through
```

## Status & limits

Built at a hackathon. The agent, the engine, and the web UI all work end to end,
including a live connector repair from F to A. The connectors ship at F on purpose
so the demo can harden them live; `git checkout presence/connectors` puts them
back. The limits worth knowing: tools are called one at a time (no create-then-read
sequences), input is OpenAPI (GraphQL and closed platforms are draft-and-hand-off),
and there's no OAuth. `architecture.md` and `business-model.md` describe an earlier
version of the project.

## Team

<!-- Add every team member's name and email here, and in the submission form. -->
