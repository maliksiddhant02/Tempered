# Tempered — Plan

*(tempering: heat it, test it, harden it — a tool is not finished until it has been proven)*

## What it is

A multi-step agent that keeps your professional presence up to date across your
apps — running on MCP connectors that Tempered generates and **proves** before
the agent is allowed to use them.

Two halves, one story:

- **The agent** (`presence/`) — tell it what's new; it drafts a post tailored to
  each platform, waits for your confirmation, and publishes. Discord, Slack,
  GitHub, Notion. BYO keys.
- **The engine** (`tempered/`) — generate a connector from an API spec, fire an
  adversarial conformance suite at it, and repair what fails. This is how you know
  the connectors work: proof, not screenshots.

"Teach the fisherman to fish": the agent can reach *any* app, because Tempered
builds and hardens the connector for it.

## One-liner

> An agent that keeps your presence current across your apps — over connectors it
> proves before it trusts.

## The brief, answered

| Requirement | How |
|---|---|
| One useful, multi-step AI agent | draft-per-platform → confirm → publish → (help reply). A real tool-use loop over MCP connectors. |
| Connect to ≥ 3 external apps | Discord, Slack, GitHub, Notion. |
| Show how you know it works | Tempered grades every connector and repairs the failing ones. |

## Judging criteria

| Criterion | Weight | What earns it |
|---|---|---|
| Technical execution | 30% | Agent loop + MCP client + generate + schema-directed eval + bounded repair, all wired into one UI. |
| Reliability & evaluation | 25% | The eval engine *is* the proof. Known-good controls, unscored ambiguity, no vacuous grades. The strongest half. |
| Usefulness | 20% | A real chore (keeping profiles/updates current) done by an agent; BYO keys; adopts today. |
| Originality | 15% | Naming and catching **silent success**, and doing it on the agent's *own* connectors — proving before trusting. |
| Demo clarity | 10% | One 2-minute arc: agent publishes → prove F → harden to A. See [DEMO.md](DEMO.md). |

## How it works

```
What's new ──▶ agent drafts per platform ──▶ you confirm ──▶ publish
                                                              │
each connector is:  API spec ──generate──▶ MCP connector ──prove──▶ grade
                                                              └─ F? ──repair──▶ A
```

- **Silent success** — a connector returns success for input its own declared
  schema forbids. The agent proceeds on garbage; nothing reaches monitoring.
- **Schema-directed synthesis** — one payload per declared constraint, each
  violating exactly one thing, so every failure is attributable and repairable.
- **The oracle** — PASS / SILENT_SUCCESS / CRASH / AMBIGUOUS, banded to A–F.
- **Repair** — bounded at two attempts, re-runs the full suite, keeps a patch only
  if it scores better, and never leaves a broken file behind.

## The four apps

Chosen for open, key/webhook auth — the "easy external apps", not an OAuth dance.

- **Discord**, **Slack** — incoming webhook, generated connectors.
- **GitHub** — token, generated connector (open an issue: title + body).
- **Notion** — token, hand-written connector (append to a page); it validates its
  schema, so it's the **positive control** (A) beside the generated ones.

Closed platforms (LinkedIn, Seek, Prosple) have no write API — the agent drafts
and hands you the text rather than pretending to auto-post.

## What proving them found

FastMCP's `from_openapi` connectors **don't enforce their declared schemas** — so
Discord/Slack/GitHub score **F** (walls of silent successes), and Notion (which
validates) scores **A**. That contrast is the demo: Tempered tells you which
connectors to trust, and `repair` hardens a failing one **F → A** in one attempt,
after which the agent still publishes valid input through it.

## Build order (what shipped)

1. Engine: synth + oracle + generate + report + CLI + web UI. *(done earlier)*
2. Repair loop, proven live F → A on the fixture.
3. Presence agent: plan/publish with the confirmation gate.
4. Connectors: Discord, Slack (webhook), GitHub (issue), Notion (page).
5. "Prove this connector" in the UI (scan against a safe sink).
6. Repair-close: "Harden" a connector F → A from the UI.

## Out of scope

- OAuth flows; closed-platform auto-posting (draft-and-hand-off instead).
- Multi-call tool sequences (create-then-read).
- A registry / catalogue.

## Risks

| Risk | Mitigation |
|---|---|
| Live third-party posting flakes on stage | Only Discord needs to post live; prove/harden run fully offline against a local sink. |
| Repair is a model call (nondeterministic) | Bounded at 2, keeps only improvements, restores on any bad candidate. Rehearse it once before the demo. |
| "You just wrapped FastMCP" | Lead with the eval engine and the F→A repair, not the generator. |
| Connectors already hardened before the demo | They ship at F; `git checkout presence/connectors` resets them. |

## Positioning

The moat is not "easy", it is **proven**. The pitch is an agent you can trust
across your apps — because every connector under it was tested and hardened, not
assumed.
