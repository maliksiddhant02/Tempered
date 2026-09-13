# Tempered

Build any AI tool from a sentence. Describe what you want, and Tempered writes the
MCP server, hands the tools to an agent you can chat with, and checks each tool
does what it claims.

The problem: an MCP server can take bad input and still reply as if it worked, so
the agent trusts a result that never happened. We call that a silent success.
Tempered throws bad input at every tool, grades what it catches, and fixes the ones
that let junk through.

## 01 · Project overview

Run `python -m tempered.cli serve` and open the live demo. There are three ways to
get a server:

- Click one of eight ready-made presets.
- Describe a tool in plain English ("a Slack poster that sends to a webhook") and
  Claude writes it.
- Paste an OpenAPI URL and Tempered builds it from the spec.

Then chat with an agent that has the server's tools: ask for something and it picks
a tool, calls the API, and answers. Open Verify to hit the tools with bad input,
see a grade, and repair whatever fails.

Everything runs on your machine. Keys stay in memory or your `.env` — never written
to disk from the browser, never sent back to the page.

## 02 · External apps used

Eight presets load straight into chat, and most need no key.

| Preset | Key needed | Try |
|---|---|---|
| Open-Meteo, weather | none | "what's the weather in Tokyo?" |
| CoinGecko, crypto prices | none | "price of bitcoin and ethereum in usd" |
| NASA, astronomy photo | none (falls back to DEMO_KEY) | "show the picture for 2024-01-01" |
| Pollinations, AI image and text | none | "generate an image of a fox in a spacesuit" |
| GitHub, REST API | reads work without one | "find popular python repos" |
| Unsplash, photo search | Unsplash access key | "find 5 photos of mountains" |
| Discord, post via webhook | a Discord webhook | "post 'hello team' to discord" |
| Petstore, OpenAPI demo | none | generates a server that scores F, then Repair takes it to A |

For anything outside this list, describe it or paste its OpenAPI URL. Keys go in
the in-page Keys panel or your `.env`, and they stay in memory. GraphQL and closed
apps (LinkedIn, Seek, Prosple) aren't generated; you draft those by hand.

## 03 · Setup instructions

```bash
python -m venv .venv
.venv/Scripts/pip install mcp fastmcp anthropic     # macOS/Linux: .venv/bin/pip
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000>. Add your Anthropic key to `.env` (see `.env.example`)
or paste it in the Keys panel, then describe a tool or load a preset. Chat uses
`claude-sonnet-4-6`.

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

Tempered sends one bad payload per schema rule, each breaking exactly one thing: a
wrong type, a missing field, an over-long value, a stray key. Reject it and the
tool passes. Accept it and that's a silent success — the bug we hunt. The pass rate
becomes a grade, A to F.

It catches real ones. Servers FastMCP generates don't enforce their own schemas, so
a fresh connector scores F. Repair rewrites it to check its input and re-runs the
scan, usually taking it F to A in one pass — and valid calls still work. The harness
plays fair too: a known-good server must score A, sensible type coercions don't
count against a tool, unreachable tools get no grade, and test writes hit a local
sink, never the real API.

The same check runs from the command line as a CI gate:

```bash
python -m tempered.cli test python path/to/server.py --fail-under B
```

It exits nonzero below the grade you set, so a regression in a spec fails the build.

## 05 · Demo video

A two-minute walkthrough link goes here once it's recorded. Notes are in
[DEMO.md](DEMO.md).

## Repo

- `tempered/` is the engine (`synth`, `scan`, `repair`, `generate`) plus the web
  app (`web`) and the CLI (`cli`).
- `tempered/static/` holds the website: the landing page and the live demo.
- `presence/` is an earlier agent that drafts and posts updates across Discord,
  Slack, GitHub, and Notion.
- `test_tempered.py` is the self-check.

Limits: one call per tool during a scan, OpenAPI in, and no OAuth.

## Team

- Siddhant Malik, co-founder (maliksiddhant02@gmail.com)
- Peter Ma, co-founder (peter.ma3@hotmail.com)
