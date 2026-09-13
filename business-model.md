# Tempered — Business Model

Osterwalder nine-block canvas. Honest version: this is a developer tool in a
young ecosystem, so the model is real but modest. Do not pitch it as a company
unless a judge asks.

## 1. Customer Segments

| Segment | Size | Pain | Priority |
|---|---|---|---|
| **Developers with an internal API** who want agents to use it, but are not MCP experts | Large and growing | Writing an MCP server by hand is a day of work they do not want | **Primary** |
| **Teams publishing MCP servers** (SaaS vendors, API companies) | Small but high value | No way to prove their server behaves correctly before shipping | Secondary |
| **Agent platform operators** ingesting third-party servers | Very small, very high value | No conformance bar. They ingest broken servers blind | Tertiary, best long-term |

Explicitly **not** a segment: non-technical users. They cannot obtain API
credentials or host a server, so removing the codegen step does not unblock them.

## 2. Value Proposition

**Verified, not easy.**

- Generate an MCP server from a spec in minutes instead of a day
- Know it works: every tool tested against adversarial input, with a published
  pass rate
- Catch **silent success** -- the failure mode where a server returns OK on
  malformed input, so the agent proceeds on garbage and nothing appears in error
  monitoring

Generation is commodity (FastMCP, Speakeasy, Stainless all do it). The
uncommoditized half is proof.

## 3. Channels

- **CLI on npm/PyPI** -- primary. `npx tempered test ./server` with an exit code
- **GitHub Action** -- conformance as a CI gate on every PR
- **Public findings** -- "we scanned N public MCP servers, X% return success on
  malformed input" is a distribution event, not just a result
- Docs and the MCP community (Discord, awesome-mcp lists)

## 4. Customer Relationships

Self-serve, open-source-first. Developer tools sell by being adopted in a
lunch break, not by demo calls. No sales motion at this stage.

## 5. Revenue Streams

Open core:

| Tier | What | Price |
|---|---|---|
| **OSS** | Generator + full eval suite + CLI | Free. This is the adoption engine, never crippled |
| **Hosted** | Continuous conformance monitoring, dashboards, history, regression alerts on spec changes | ~$20-50/mo per team |
| **Certification** | A public "verified" badge with an audit trail, for vendors publishing servers | Per-server annual fee |
| **Enterprise** | Self-hosted, private registry, SSO, custom checks | Annual contract |

Honest read: **nobody pays for this today.** The ecosystem is too young and the
volume of servers per team is too low. Revenue only closes if MCP becomes
standard infrastructure and teams run dozens of servers. That is a real bet, not
a certainty -- say so if asked rather than inflating a TAM.

## 6. Key Resources

- The eval suite itself -- the schema-directed payload synthesis engine
- The corpus of scanned public servers and their failure patterns (compounds over
  time, and nobody else has it)
- Protocol expertise as MCP evolves

## 7. Key Activities

- Maintaining the eval suite against a moving protocol spec
- Keeping false positives near zero -- a checker that flags correct servers is
  worse than no checker
- Publishing findings to sustain the conformance-bar narrative

## 8. Key Partnerships

- **FastMCP / generation tooling** -- dependency, not competitor. Tempered makes
  their output trustworthy
- **MCP registries** (official, Smithery, mcp.so) -- natural integration: show a
  conformance grade next to each listing
- **Agent platforms** -- the endgame. If a platform adopts the suite as its
  ingestion bar, it becomes the standard

## 9. Cost Structure

Near zero. A CLI and a static report page. Real costs appear only at the hosted
tier: LLM inference for the describability check plus compute for continuous
scans. Both scale with paying usage, not with free adoption.

---

## Competitive position

| Piece | Already exists | Us |
|---|---|---|
| OpenAPI -> MCP generation | FastMCP, Speakeasy, Stainless, gateway converters | We consume it, we do not rebuild it |
| MCP registries | Official registry, Smithery, PulseMCP, mcp.so | Not competing. We supply the grade |
| MCP server testing | MCP Inspector (manual poking) | Automated adversarial suite. **This is the gap** |
| Eval-gated publishing + repair | Nothing shipped | **The product** |

**Defensibility is weak at first** and should be stated plainly: an incumbent
generator could bolt on testing. What compounds is the failure corpus and being
the reference bar the ecosystem cites -- standards win by adoption, not features.

## Why this is not a moat

- *"Non-technical users cannot do this"* -- ease of use is a weekend of UI work
  for any incumbent, and the persona cannot use the output anyway
- *"We generate MCP servers"* -- commodity, several mature tools already ship it

## What is actually defensible

- Being the **conformance bar** the ecosystem cites
- The **failure corpus** across thousands of scanned servers
- **Silent success** as named, understood vocabulary. Naming a defect class is
  how a tool becomes the default answer to it
