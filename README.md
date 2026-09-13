# Tempered

An agent that posts your updates across Discord, Slack, GitHub, and Notion, over
connectors it tests before it trusts them.

## 01 · Project overview

Tell it what's new. It drafts a post for each platform, you confirm, it publishes.

The catch with pointing an agent at real apps: an MCP connector can take malformed
input and still return success, so the agent acts on garbage and nothing errors. We
call that a silent success. Tempered's engine builds each connector from an API
spec, attacks it with bad input, grades it, and repairs it, so the agent only uses
connectors that pass.

## 02 · External apps used

| App | Connector | Action |
|---|---|---|
| Discord | generated from an OpenAPI spec | post via incoming webhook |
| Slack | generated from an OpenAPI spec | post via incoming webhook |
| GitHub | generated from an OpenAPI spec | open an issue (REST API) |
| Notion | hand-written adapter | append to a page |

Simple key/webhook auth, no OAuth. Keys are yours: entered in the UI, kept in
memory. Closed apps (LinkedIn, Seek, Prosple) get a draft you paste yourself.

## 03 · Setup instructions

```bash
python -m venv .venv
.venv/Scripts/pip install mcp fastmcp anthropic     # macOS/Linux: .venv/bin/pip
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000>, paste your Anthropic key and a Discord webhook under
**Connections & keys**, type what's new, hit **Draft**, then **Publish approved**.
**Prove** grades a connector; **Harden** repairs a failing one.

## 04 · Reliability testing

```bash
python test_tempered.py
```

```
  good_server      A 100% over 20 checks
  broken_server    F 5%, 18 silent successes caught
  control          identical 20-check contract, opposite verdicts
  write safety     POST skipped by default, scanned with --allow-writes
```

For each tool's schema, Tempered sends one payload per rule, each breaking exactly
one thing (wrong type, missing field, over the length limit, a stray key). A proper
error is a pass; a success reply to bad input is a silent success, the bug we hunt.
The pass rate becomes a grade, A to F.

It caught a real one. FastMCP's generated connectors don't enforce their schemas,
so Discord, Slack, and GitHub score F; the hand-written Notion one validates and
scores A. `repair` rewrites a failing connector to validate its input, taking it
from F to A in one pass while it still publishes valid posts. The harness stays
honest too: a known-good server must score A, sensible coercions are unscored,
unreachable tools get no grade, and adversarial writes hit a local sink during
testing, never the real API.

## 05 · Demo video

▶ **[Add your ≤2-minute link here]** — walkthrough in [DEMO.md](DEMO.md).

## Repo

`presence/` is the agent (draft, confirm, publish); `tempered/` is the engine
(`synth` → `scan` → `repair` → `generate`, plus `web`/`cli`). `test_tempered.py` is
the self-check. Connectors ship at F so the demo can harden them live;
`git checkout presence/connectors` resets them. Limits: one call per tool, OpenAPI
in (GraphQL and closed apps are draft-only), no OAuth.

## Team

- peter.ma3@hotmail.com
<!-- add the rest of the team here and in the submission form -->
