# Anvil — Architecture

Scope note: this is a two-day hackathon build. The architecture is deliberately
small. No database, no services, no queue. If a section of this document starts
growing infrastructure, it is wrong.

## 1. Understand

**Problem.** MCP servers commonly return a normal success result when handed
malformed input. The calling agent proceeds on garbage, nothing is raised, and
nothing appears in error monitoring. There is no automated way to detect this.

**What we build.** A pipeline that generates an MCP server from an OpenAPI spec,
proves each tool behaves correctly under adversarial input, repairs what fails,
and publishes a grade.

**Constraints.**

- Two days, small team
- Must run live on stage in under three minutes
- Must not perform destructive writes against real third-party APIs
- Deterministic where possible: the same server scanned twice gives the same result

**Non-goals.** Registry infrastructure, accounts, persistence, hosting, any input
source other than OpenAPI, stateful multi-call test sequences.

## 2. Research

| Concern | Decision | Why |
|---|---|---|
| Language | **Python 3.11+** | FastMCP and the first-party MCP SDK are Python. TypeScript is viable but we would rebuild more |
| Generation | **FastMCP `from_openapi()`** | Commodity. Rebuilding it spends the hours the eval suite needs |
| Schema walking | `jsonschema` + hand-rolled mutation | Off-the-shelf fuzzers generate *valid* data; we need targeted invalid data |
| Transport | stdio first, HTTP second | stdio is what local servers use and is easiest to drive |
| Repair | LLM patch against the failing check | Bounded, diffed, re-verified |
| Report | Static HTML, one file | A catalogue scores zero points |

## 3. Specify

### Pipeline

```
OpenAPI spec
    |
    v
generate  ---> MCP server (source on disk)
    |
    v
client    ---> spawn, initialize, tools/list
    |
    v
synth     ---> N adversarial payloads per tool, one violation each
    |
    v
checks    ---> call each, classify response
    |
    +-- all pass --> report (grade + pass rate)
    |
    v
repair    ---> patch, re-run FULL suite, max 2 attempts, else mark failed
```

### Module layout

```
anvil/
  cli.py         entrypoint, exit codes
  generate.py    OpenAPI -> MCP server (thin wrapper over FastMCP)
  client.py      MCP protocol client: stdio + HTTP, handshake, timeouts
  synth.py       schema-directed payload synthesis      <- the core engineering
  checks/
    silent_success.py
    drift.py
    error_surfacing.py
    coercion.py
    side_effects.py
    describability.py    (LLM-judged, optional)
  repair.py      failure -> patch -> re-verify, bounded at 2
  report.py      render one static page
```

### Core algorithm: schema-directed payload synthesis

This is what makes it a system rather than a script, and it is the 30% criterion.
For each tool's declared `inputSchema`, walk every constraint and emit a payload
that violates **exactly one** of them, leaving everything else valid.

| Constraint in schema | Violation emitted |
|---|---|
| `type: string` | integer, null, array |
| `type: integer` | `"5"` (string numeral), float, null |
| `required: [x]` | omit `x` |
| `enum: [a, b]` | a value outside the enum |
| `minimum` / `maximum` | out of bounds by one |
| `minLength` / `maxLength` | empty string / oversized string |
| `format` (email, uri, date-time) | malformed string of the right type |
| `additionalProperties: false` | an extra unexpected key |
| nested `object` | recurse into properties |
| `array` with `items` | wrong-typed element, empty array |

**One violation per payload** is the load-bearing rule. Two violations in one
payload make a failure unattributable, and unattributable failures cannot be
repaired automatically.

### The oracle

A conformant server, given any of the above, must return either a JSON-RPC error
or a result with `isError: true`.

| Observed response | Verdict |
|---|---|
| JSON-RPC error, or `isError: true` | **PASS** |
| Normal content result | **SILENT SUCCESS** -- the headline finding |
| Server crashes or hangs | **CRASH** -- worse than a failed check, reported separately |
| Value coerced and handled sanely (`"5"` becomes `5`) | **AMBIGUOUS** -- reported, not counted as failure |

The AMBIGUOUS class exists on purpose. A checker that flags correct servers is
worse than no checker, so anything the MCP spec does not clearly define is
reported as ambiguity rather than scored as a violation.

### Safety: destructive tools

Adversarial input must never be sent to a real destructive endpoint. Generated
tools carry the HTTP method from the spec.

- Default: **only** `GET`/`HEAD` tools are called against live third-party APIs
- `POST`/`PUT`/`PATCH`/`DELETE` tools are exercised against a local mock unless
  `--allow-writes` is passed explicitly
- Stripe test mode is the exception and is why it is app #1: real writes, no
  real consequences

### Data shapes

```python
Finding   = {tool, check, verdict, constraint_violated, payload_sent, response}
ToolScore = {tool, checks_run, checks_passed, findings[]}
Report    = {server, grade, pass_rate, tools[], generated_at}
```

Grade is a band over pass rate (A >= 95%, B >= 85%, C >= 70%, D >= 50%, else F).
`anvil test ./server --fail-under B` exits nonzero below the threshold, which is
what makes it adoptable in CI.

### Repair contract

- **In:** failing finding + server source + observed response
- **Out:** a patch to the schema or the handler
- **Bounded at 2 attempts**, then the tool is marked failed and left failed
- After every patch, **re-run the full suite, not just the failing check** --
  otherwise a fix for one check silently breaks another
- The diff is surfaced, not hidden. Judges score the reasoning, not the light
  turning green

## 4. Decompose

| # | Component | Depends on | Risk | Notes |
|---|---|---|---|---|
| 1 | `client.py` | -- | Medium | Protocol handshake and timeouts. Everything blocks on this |
| 2 | `synth.py` | -- | **High** | The core engineering. Buildable in parallel with the client |
| 3 | `checks/` (4 deterministic) | 1, 2 | Low | Mechanical once the first two land |
| 4 | `generate.py` | -- | Low | Thin FastMCP wrapper. Parallelizable from hour zero |
| 5 | `repair.py` | 1-4 | Medium | LLM in the loop, nondeterministic |
| 6 | `report.py` + `cli.py` | 3 | Low | One static page, exit codes |
| 7 | `describability.py` | 1, 4 | Low | Cut first if hours run short |

Components 1, 2, and 4 have no dependencies on each other and should be built
simultaneously.

## 5. Plan

**Critical path:** `client.py` -> `synth.py` -> `checks/` -> app #1 end to end.

1. `client.py` and `synth.py` in parallel, plus `generate.py` on the side
2. Wire the four deterministic checks
3. **App #1 (Stripe test mode) end to end** -- generate, fail, repair, pass
4. `report.py` + CLI exit codes
5. Apps #2 (Slack) and #3 (Linear)
6. Cross-app agent task for the demo close
7. `describability.py` only if time remains

**The floor is step 3.** One app generated, failed, repaired, passing, and called
by an agent is a complete story. Stop adding apps before that is solid.

## Verification

Non-negotiable, because we are grading our own homework and judges discount that:

- **Known-good control** -- one server we have verified is correct, which the
  suite passes cleanly. Proves the harness does not simply flag everything
- **One third-party hand-written server** in the scan set. Findings against code
  we did not write are the credible ones
- **Determinism check** -- same server, two runs, identical report

## Open questions

| Question | Current answer |
|---|---|
| Auth injection into generated servers | Env vars per app, hardcoded for the demo. Do not generalize |
| Stateful APIs (create then read) | Out of scope. Single-call tools only |
| Pagination, file upload, OAuth flows | Out of scope. Say so if asked; it is the honest generalization ceiling |
| LLM nondeterminism in repair | Bounded retries, and repair runs live only for app #1 |
