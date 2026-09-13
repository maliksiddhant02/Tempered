# Deploying Tempered to Render

The full app (landing + demo + backend) on one URL. Free tier fits.

## Prereqs

1. This repo pushed to GitHub (public or private, either works).
2. A [Render account](https://render.com) — GitHub sign-in is easiest.
3. Your `ANTHROPIC_API_KEY` handy.

## Deploy

1. In the Render dashboard: **New → Web Service**.
2. Connect your GitHub, pick the Tempered repo.
3. Render reads `render.yaml` and auto-fills most fields. Confirm:
   - **Runtime**: Python
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `python -m tempered.cli serve`
   - **Plan**: Free
4. Under **Environment**, paste values for the keys marked `sync: false`:
   - `ANTHROPIC_API_KEY` — required
   - Others — only the ones your demo uses
5. Click **Create Web Service**. First build takes ~3 minutes.
6. When it's live, Render shows a URL like `https://tempered-xxxx.onrender.com`.

## Verify

- Open the URL → landing page loads.
- Click **See the live demo →** → demo page loads.
- The "Keys" panel should show ✓ ANTHROPIC_API_KEY loaded.
- Type a description, hit Generate. Chat should work.

## Free-tier gotchas

- Service **sleeps after 15 min of inactivity**. First request after sleep takes ~30s to wake. Warm it up before showing judges.
- **Ephemeral filesystem**: `generated/` is wiped on restart. Fine for a demo.
- **512 MB RAM**: enough for this. Big MCP servers (huge OpenAPI specs) may OOM.

## Cost / security warnings

- **Anyone with the URL can hit `/api/describe` and `/api/chat`**, burning your Anthropic credits. Options:
  - Take the service down after judging (Render dashboard → Suspend).
  - Set a spending limit in your Anthropic console.
  - Add a shared-secret header (not implemented yet — ask if you want it).
- **Discord/Slack webhooks are the same**: anyone hitting your deployed app can post to them.

## Updating

Push to `main` — Render auto-redeploys on every commit.

## Rollback

Render → your service → **Deploys** tab → click any previous deploy → **Redeploy**.

## Taking it down

Render → your service → **Settings** → **Suspend Web Service**. Free tier costs nothing suspended.
