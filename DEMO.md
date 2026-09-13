# Tempered — 2-minute demo

## Before you start (once)

```bash
python -m tempered.cli serve
```

Open <http://127.0.0.1:8000> → **Connections & keys** → paste:
- **Anthropic API key** (required for Draft and Harden)
- **Discord webhook URL** (required for a real post — Server Settings →
  Integrations → Webhooks → New)

Prove and Harden work with **no keys at all** (they run against a local sink), so
even with nothing but the Anthropic key you can do the whole engine half.

Make sure the connectors are at their generated **F** state (they ship that way):

```bash
git checkout presence/connectors
```

## The run (≈2:00)

**1 · The agent (0:00–1:00).**
Type into *What's new*: *"I open-sourced Tempered, a tool that generates MCP
connectors from an API spec and proves they reject bad input before you ship."*
Tick **Discord** (+ Slack/GitHub if you set them up). **Draft.**
> "One agent, several apps. It writes a post tailored to each platform, and it
> won't invent facts — only what I gave it."

Edit a word to show they're yours, then **Publish approved.**
> "Nothing goes out until I approve it." → the post appears in the real Discord channel.

**2 · The proof (1:00–1:40).**
> "These connectors were generated from API specs. Can you trust them?"
**Prove Discord** → red findings stream in, grade **F**.
> "FastMCP's generated connector accepts an integer where it declared a string, a
> message past its length limit, a missing required field — and returns success.
> The agent would never know. This connector doesn't enforce its own contract."

**Prove Notion** → **A**.
> "A connector that *does* enforce its schema passes. Tempered isn't flagging
> everything — it tells you which ones you can trust."

**3 · The close (1:40–2:00).**
**Harden Discord** → the diff streams, **F → A**.
> "One click: Tempered rewrites it to validate its schema, then re-proves it — A.
> Generate a connector for any app, prove it, harden it, then let the agent use
> it. That's Tempered."

## Talking points if pressed

- **"So your connectors are broken?"** — They're *generated*, and generation is
  commodity. The point is Tempered *catches* that they don't validate and *fixes*
  it. That's the product.
- **"F just means Discord rejects it?"** — No. F means the *connector* doesn't
  enforce its declared schema; it forwards downstream regardless. That's exactly
  the failure that never reaches error monitoring.
- **Reliability** — a known-good control (`good_server`, and Notion) must score A,
  ambiguous cases are unscored, untestable tools don't count. It doesn't just
  flag everything.

## Reset between runs

```bash
git checkout presence/connectors    # restore the connectors to F
```
