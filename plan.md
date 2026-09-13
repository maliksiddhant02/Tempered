# Anvil — Plan

*(working name: forge the tool, then test it on the anvil)*

## What it is

An agent that builds MCP servers for other apps, proves they work, and then uses
them. Point it at an API's OpenAPI spec: it generates a working MCP server, runs
an adversarial eval suite against every tool, repairs what fails (bounded at two
attempts), and publishes it with a pass rate. Do that for three apps, then let an
agent complete one real task spanning all three.

## One-liner

> Most MCP servers return success on malformed input, so agents fail silently.
> This one builds them *and* proves they work before shipping.

## The brief, answered

| Requirement | How |
|---|---|
| One useful, multi-step AI agent | The generate -> eval -> repair -> publish loop. Real agent loop, real failure handling |
| Connect to >= 3 external apps | Stripe (test mode), Slack, Linear |
| Show how you know it works | The eval suite. Per-tool pass rates, not claims |

The third requirement is the whole product, not a closing slide. That is the
differentiator.

## Judging criteria

| Criterion | Weight | Est. | What earns it |
|---|---|---|---|
| Technical execution | 30% | 8 | Generator + eval + repair loop + three live integrations |
| Reliability & evaluation | 25% | 9 | The eval suite *is* the product |
| Usefulness | 20% | 8 | Every agent dev with an unwrapped API; cross-app task makes it concrete |
| Originality | 15% | 7 | Capped: generation is commodity, eval-gated publishing is the fresh part |
| Demo clarity | 10% | 8 | One story, but three apps is a lot of narrative for 3 min |
| **Weighted** | | **8.10/10** | |

### One lever per criterion

- **Technical execution (30%)** — Derive bad payloads *from the schema*, never
  hardcode them. Walk the JSON Schema, synthesize a violation per constraint:
  wrong type, out-of-enum, missing required, out-of-bounds, bad format, extra
  keys. A fixed list of five bad inputs is a script; this is a system. Say
  "schema-directed" out loud in the demo.
- **Reliability (25%)** — We grade our own homework and judges discount that.
  Two cheap fixes: run the suite against one *hand-written* MCP server (not
  ours), and ship a **known-good control** the harness passes cleanly, proving it
  does not just flag everything.
- **Usefulness (20%)** — CLI with an exit code, not a web app.
  `npx anvil test ./server --fail-under B` returning nonzero is adoptable Monday.
- **Originality (15%)** — Name the defect class. "**Silent success**" is what a
  judge repeats in deliberation. Do not oversell the generator; anyone who knows
  FastMCP will discount it.
- **Demo clarity (10%)** — Pre-generate apps #2 and #3. Only app #1 generates
  live, so a cold API cannot sink the demo.

## How it works

```
OpenAPI spec
    |
    v
[1] Generate      tool schemas + handlers (FastMCP from_openapi as the base)
    |
    v
[2] Eval          schema-directed adversarial suite, every tool
    |
    +-- pass --> [4] Publish with pass rate
    |
    v
[3] Repair        patch schema or handler, re-run. Max 2 attempts, then mark failed
```

## Architecture

Four components, deliberately small:

| Component | Does | Notes |
|---|---|---|
| `generate` | OpenAPI -> MCP server | Wraps FastMCP `from_openapi()`. Do not rebuild this |
| `eval` | Adversarial suite over a live server | The real engineering. Schema-directed payload synthesis + protocol client (stdio + HTTP) |
| `repair` | Failure -> patch -> re-run | Bounded at 2. Emits a visible diff |
| `report` | One page, per-server grade + per-check detail | Not a registry. One page |

### What the eval suite checks

| Check | Catches | LLM needed |
|---|---|---|
| Silent success | Malformed payload returns content with no `isError`. Agent believes it worked. **Headline finding** | No |
| Schema/handler drift | Declared `required` field the handler ignores; declared types never enforced | No |
| Error surfacing | Upstream 4xx/5xx arrives as a cheerful string instead of an MCP error | No |
| Type coercion | `"5"` vs `5`, null vs missing, empty array, extra keys | No |
| Describability | Can a model pick the right tool from descriptions alone, with distractors? Nobody tests this | Yes |
| Side-effect labeling | Does a destructive tool announce itself before an agent calls it? | No |

Four of six need no LLM: deterministic, fast, safe to run live on stage.

## The three apps

Chosen on **auth simplicity**, not brand recognition. An OAuth dance will eat the
hackathon.

- **Stripe** (test mode) — safe real writes against a real API, kills the
  mock-data penalty outright
- **Slack** — clean token auth
- **Linear** — clean token auth

Swap candidates if auth fights back: GitHub, Todoist, Resend, Airtable.

Cross-app task: *payment fails in Stripe -> open a Linear issue with customer
details -> post the thread to Slack.* One sentence, obviously useful, visibly
multi-step.

## Build order

1. **Eval suite** — schema-directed payload synthesis + MCP protocol client
2. **Generator** — OpenAPI in, server out, via FastMCP
3. **Repair loop** — bounded at 2, emits a visible diff
4. **App #1 end to end** — generate, fail, repair, pass, agent calls it
5. **Apps #2 and #3**
6. **Report page + CLI exit codes**
7. **Describability judge** — only from leftover time

### The floor

**A credible entry stops at step 4.** One app generated, failed, repaired,
passing, and called by an agent is a complete story. Three shallow integrations
lose to one deep one plus two that merely work.

### Hour allocation

Allocate to weight, not enthusiasm:

- **50%** generator + schema-directed eval suite *(the 55% of score that decides this)*
- **20%** repair loop + known-good control
- **15%** the three integrations
- **15%** CLI packaging + demo rehearsal

## Demo script (3 min)

1. Paste the Stripe spec. Server generates. **Tools fail red.** Repair runs.
   **Green.** Show the patch diff on screen -- red/green is a light, the diff is
   engineering.
2. Slack and Linear already sitting in the report with pass rates (pre-generated).
3. Agent runs one task through all three: payment fails -> Linear issue -> Slack post.

No slides before the terminal.

## Out of scope

Cut without hesitation. None of it touches any of the five criteria:

- Registry infrastructure (a catalogue scores zero and eats days)
- Non-technical onboarding UX (ease of use is a feature, not a moat; the persona
  cannot get API credentials anyway)
- Docs-page and CLI `--help` input inference (LLM-flaky, zero extra points)
- Any input source beyond OpenAPI
- Auth, accounts, persistence

## Risks

| Risk | Mitigation |
|---|---|
| Scope: four components + three apps is wide | Hold the floor at step 4. Apps #2/#3 are additive, never blocking |
| Live LLM generation is slow and nondeterministic on stage | Only app #1 generates live. Pre-generate the rest |
| An API that generates cleanly first try = no story | Pick a spec verified to fail the first pass. Seed the failure |
| Judges discount self-graded evals | Known-good control + test one hand-written third-party server |
| "You just wrapped FastMCP" | Lead with the eval suite, not the generator. The generator is a dependency, not the pitch |

## Positioning

The moat is not "easy", it is **verified**. Do not pitch accessibility -- pitch
proof. The audience is the competent developer who is not an MCP expert and has
an internal API to expose, not a non-technical user.
