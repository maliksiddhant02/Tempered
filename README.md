# Tempered

Describe an API in plain English. Tempered writes an MCP server for it, hands the
tools to a Claude-powered agent you can chat with, and tests every tool for the
failure mode where servers accept broken input and reply as if it worked. We call
that silent success. It is the reason agents lie about results that never happened.

## Demo video

*A two-minute walkthrough will be linked here once recorded.*

Live deployment: *URL added after Render deploy.*

## What Tempered does

There are three ways to get an MCP server:

1. Pick one of the eight built-in presets. Most need no API key.
2. Type an English description ("a Slack poster that sends to a webhook"). Claude
   writes the FastMCP server file.
3. Paste an OpenAPI URL. Tempered generates a server from the spec via FastMCP.

The chat panel opens with the new server's tools loaded. Ask the agent to do
something, it picks the right tool, calls the API, and answers.

Below the chat, a Verify panel runs the adversarial suite. It fires one broken
payload per schema rule at every tool, grades what the server catches, and offers
Repair to rewrite anything that fails.

Everything runs on your machine or your own hosting. API keys live in your
`.env` file or the in-memory Keys panel. Nothing is written back to disk from
the browser.

## Quick start

```
git clone <repo-url>
cd Tempered
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# edit .env, add ANTHROPIC_API_KEY at minimum
python -m tempered.cli serve
```

Open http://127.0.0.1:8000 and click "See the live demo".

## Deploy

The full stack (landing, demo, backend) runs on any host that supports Python and
subprocess spawning. `render.yaml` and `requirements.txt` are included.

See [DEPLOY.md](DEPLOY.md) for click-by-click Render instructions. Free tier
fits; first build takes about three minutes.

## Presets

| Preset | Key needed | Try it with |
|---|---|---|
| Open-Meteo, weather | none | "what's the weather in Tokyo" |
| CoinGecko, crypto prices | none | "price of bitcoin and ethereum in usd" |
| NASA astronomy photo | falls back to DEMO_KEY | "show the picture for 2024-01-01" |
| Pollinations, AI image and text | none | "generate an image of a fox in a spacesuit" |
| GitHub REST | reads work without a token | "find popular python repos" |
| Unsplash photo search | `UNSPLASH_ACCESS_KEY` | "find 5 photos of mountains" |
| Discord post | `DISCORD_WEBHOOK_URL` | "post hello team to discord" |
| Petstore, OpenAPI demo | none | starts at F, Repair takes it to A |

For anything else, describe it or paste its OpenAPI URL. GraphQL and OAuth-only
APIs (LinkedIn, closed platforms) are not covered.

## How it works

Four small components, plus a UI on top.

**`generate`** turns an OpenAPI spec into an MCP server via FastMCP. Nothing
custom on top.

**`synth`** walks the JSON schema of every tool and emits one adversarial payload
per single-constraint violation: wrong type, out-of-enum, missing required field,
above or below bounds, malformed format, extra key on a closed object. One
violation per payload is load-bearing. Two violations at once make a failure
unattributable, and unattributable failures cannot be repaired automatically.

**`scan`** spawns the server over stdio, calls each tool with a valid baseline
first, then with each violation payload. The oracle:

| Server response to invalid input | Verdict |
|---|---|
| JSON-RPC error, or `isError: true` | Pass. Rejected correctly. |
| Normal success result | Silent success. The headline finding. |
| Timeout or crash | Crash. |
| Coerced and handled sensibly | Ambiguous. Reported, excluded from score. |

Pass rate bands into a letter grade: A at 95%, B at 85%, C at 70%, D at 50%,
otherwise F.

**`repair`** hands the failing checks to Claude, expects a rewritten server that
enforces its own schema, and re-runs the FULL suite. If the new score is worse,
the patch is thrown out. Bounded at two attempts.

**`describe`** takes an English description, hands it to Claude with a strict
FastMCP-server template, and writes a runnable Python file to `generated/`. The
same chat and scan tools apply.

## Reliability

The self-check runs against fixtures that declare an identical schema:

```
python test_tempered.py
```

```
good_server      A 100% over 20 checks
broken_server    F 5%, 18 silent successes caught
control          identical 20-check contract, opposite verdicts
write safety     POST skipped by default, scanned with --allow-writes
```

The harness plays fair:

- Known-good fixtures must score A. If one drops, the self-check fails loudly.
- Ambiguous behaviours (coercing `"5"` to `5`, ignoring unknown keys) get their
  own verdict rather than counting against a server.
- A tool that rejects its own valid example is marked inconclusive and excluded
  from grading. Otherwise an unreachable server would score 100% for rejecting
  everything.
- Write tools (POST, PUT, DELETE, PATCH) are skipped unless `--allow-writes` is
  passed. Even then, generated Discord and Slack connectors are pointed at a
  local sink during scans so nothing hits real APIs.

As a CI gate:

```
python -m tempered.cli test python path/to/server.py --fail-under B
```

Exit code is nonzero below the grade you set, so a spec regression fails the build.

## Future vision

The generator is commodity. Several tools already turn OpenAPI into MCP. The
uncommoditised half is proof: knowing which servers reject what they should. That
is where Tempered goes next.

**Near term**

- More verified presets. Every entry is a preselected spec that has passed the
  suite end to end.
- A GitHub Action wrapping `tempered test` so a schema regression in a pull
  request fails CI without any config beyond a single line in a workflow file.
- A shared-secret header for the deployed backend so a public demo URL cannot be
  abused by anyone who finds it.

**Mid term**

- Continuous conformance monitoring. Watch every published MCP server for schema
  drift and silent-success regressions, alert on the ones that stop rejecting
  what they should.
- A public verified badge with an audit trail, embeddable next to any MCP server
  listing (Smithery, mcp.so, the official registry).
- A private tier for teams: history, dashboards, custom checks against internal
  APIs.

**Long term**

- Adoption by MCP registries and agent platforms as the ingestion bar. Broken
  servers stop reaching agents in the first place.
- A named vocabulary for MCP failure modes (silent success, schema drift,
  describability collapse) that becomes standard usage in tooling, docs and
  post-mortems. Standards win by adoption, not by features.

## Repo layout

```
tempered/
  synth.py         schema-directed payload synthesis (the core)
  client.py        MCP protocol client over stdio
  scan.py          oracle: run, classify, grade
  repair.py        bounded patch loop with full re-verify
  generate.py      OpenAPI to server plus method manifest
  web.py           local UI, SSE-streamed scans and chat
  static/          landing page, demo page, styles
  cli.py           test | repair | generate | serve
generated/         generated MCP servers (gitignored)
fixtures/          good and broken servers for the self-check
test_tempered.py   end-to-end self-check
requirements.txt   pinned deps for deploy
render.yaml        Render web-service config
DEPLOY.md          deploy walkthrough
```

## Known limits

- One call per tool during a scan. Sequences like create-then-read are not tested.
- OpenAPI input only. GraphQL and recorded traffic are obvious next ingest paths.
- No OAuth flow support. Bearer tokens and webhook URLs work.
- LLM-written servers only cover APIs Claude knows well from training. Niche or
  post-cutoff APIs will get hallucinated endpoints and 404 on real calls.

## Team

- Siddhant Malik, co-founder. maliksiddhant02@gmail.com
- Peter Ma, co-founder. peter.ma3@hotmail.com

## License

See [LICENSE](LICENSE).
