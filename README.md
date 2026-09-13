# Tempered

**A multi-step agent that keeps your professional presence current across your
apps — over connectors it *proves* before it trusts them.**

*Tempering: heat it, test it, harden it — a tool is not finished until it has been proven.*

---

## 01 · Project overview

Keeping your presence up to date across the places that matter — a community
Discord, a team Slack, GitHub, a Notion profile page — is a recurring chore, and
wiring an agent to each app means trusting connectors nobody checked.

**Tempered is two halves that solve both problems:**

- **The agent** (`presence/`) — tell it what's new; it drafts a post tailored to
  each platform, waits for your confirmation, and publishes. Draft → confirm →
  publish, across every connected app, using only facts you gave it.
- **The engine** (`tempered/`) — generates an MCP connector for an app from its
  API spec, fires an adversarial conformance suite at it, grades it, and repairs
  what fails. The agent only uses connectors that have been **proven**.

The problem it really solves: an MCP server declares a JSON Schema for each tool
but nothing makes it *enforce* that schema. A connector can accept malformed input
and return success — the agent proceeds on garbage, and nothing reaches error
monitoring. Tempered calls this **silent success** and is built to catch it. "Teach
the fisherman to fish": the agent can reach *any* app, because Tempered builds and
hardens the connector for it.

## 02 · External apps used

The agent connects to **four** external apps, chosen for open key/webhook auth:

| App | Connector | Action |
|---|---|---|
| **Discord** | generated from an OpenAPI spec | post an update via an incoming webhook |
| **Slack** | generated from an OpenAPI spec | post an update via an incoming webhook |
| **GitHub** | generated from an OpenAPI spec | open an issue (title + body) via the REST API |
| **Notion** | hand-written adapter | append an update to a page (nested block API) |

All are reached through the Model Context Protocol (stdio). Credentials are
bring-your-own, entered in the UI and held in memory only. Closed platforms with
no write API (LinkedIn, Seek, Prosple) are handled honestly — the agent drafts the
text and hands it to you rather than pretending to auto-post.

## 03 · Setup instructions

```bash
python -m venv .venv
.venv/Scripts/pip install mcp fastmcp anthropic          # Windows; use .venv/bin/pip on macOS/Linux
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000> and:

1. Expand **Connections & keys** → paste your **Anthropic API key** and a
   **Discord webhook URL** (Discord → Server Settings → Integrations → Webhooks →
   New Webhook → Copy URL). Add Slack/GitHub/Notion keys the same way if you want
   those apps. **Save keys.**
2. Type what's new, tick the platforms, **Draft**.
3. Edit the drafts if you like, then **Publish approved** — it posts to your real
   channels. Nothing is sent until you click.
4. **Prove** any connector to see its conformance grade; **Harden** a failing one
   to watch Tempered rewrite it and re-prove.

The server binds to `127.0.0.1` only, deliberately: scanning a connector spawns
the process that runs it, so this endpoint executes commands. It is a local tool,
not something to expose on a network.

## 04 · Reliability testing

Reliability *is* the product — the engine exists to prove the connectors work, so
"how we know it works" is a first-class feature, not an afterthought.

**One command, end to end:**

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

**How the eval works.** For each tool's declared schema, Tempered walks every
constraint and synthesizes a payload that violates **exactly one** of them (wrong
type, out of enum, missing required, out of bounds, bad format, extra key). One
violation per payload is load-bearing: two would make a failure unattributable,
and unattributable failures cannot be repaired automatically. Each response is
classified by an oracle — JSON-RPC error / `isError` → **PASS**; a normal success
result → **SILENT SUCCESS** (the headline defect); timeout/crash → **CRASH**;
sensible coercion → **AMBIGUOUS** (reported, not scored). The pass rate bands to a
grade: A ≥ 95%, B ≥ 85%, C ≥ 70%, D ≥ 50%, else F.

**We proved the real connectors — and it found something.** FastMCP's
`from_openapi` connectors do **not** enforce their declared schemas; they forward
an integer where a string was declared, a message past its length limit, a missing
required field, all returning success. So Discord/Slack/GitHub score **F**. The
hand-written Notion connector, which validates, scores **A** — the positive
control. Tempered doesn't flag everything; it tells you which connectors to trust.

**And it repairs them.** `repair` rewrites a failing connector into explicit tools
that validate the schema, then make the same request — verified **F → A** in one
attempt, with the hardened connector still publishing valid input. Bounded at two
attempts, re-runs the full suite after every patch, keeps a patch only if it scores
better, and restores the original if a candidate won't even run.

**We don't trust our own harness blindly** — a checker that flags correct servers
is worse than none:

- **Known-good controls ship with the repo.** `fixtures/good_server.py` (and
  Notion) must come back clean; the self-check fails if they ever don't.
- **Ambiguity is unscored**, not counted against a server.
- **Untestable ≠ passing.** A tool that rejects its own valid example is
  `INCONCLUSIVE`; a reachable tool with nothing to violate earns no grade — no
  vacuous A.
- **Writes are safe.** `generate` records each tool's HTTP method; the scanner
  skips non-GET tools unless you pass `--allow-writes`. Proving a connector points
  it at a local sink first, so adversarial writes never reach the real API.

## 05 · Demo video

▶ **[Add your ≤2-minute demo link here]**

The run-through it follows is scripted in [DEMO.md](DEMO.md): the agent drafts and
publishes across platforms → **Prove Discord** (F, silent successes) → **Prove
Notion** (A) → **Harden Discord** (F → A).

---

## How it works

```
What's new ──▶ agent drafts per platform ──▶ you confirm ──▶ publish
                                                              │
each connector:  API spec ──generate──▶ MCP connector ──prove──▶ grade
                                                              └─ F? ──repair──▶ A
```

The agent's `plan()` runs the model with the connectors' publish tools available
but **executes nothing** — each call is intercepted and recorded as a proposal
(the multi-step, per-platform drafting). `publish()` runs only the proposals you
approved, injecting BYO secrets the model never sees. The gap between them is the
confirmation gate.

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
  cli.py              test | repair | generate | serve
fixtures/             good (A) and broken (F) — identical contract, opposite verdicts
test_tempered.py      end-to-end self-check
DEMO.md               the 2-minute run-through
```

## Status & limits

Built at a hackathon; agent, engine, and web UI verified end to end, including a
live connector repair **F → A**. Connectors ship at F on purpose — the demo hardens
them live; `git checkout presence/connectors` resets them. Limits: single-call
tools (no create-then-read); OpenAPI in (GraphQL and closed platforms are
draft-and-hand-off); no OAuth flows. `architecture.md` and `business-model.md`
describe an earlier framing of the project.

## Team

<!-- Add every team member's name and email here, and in the submission form. -->
