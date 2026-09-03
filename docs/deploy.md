# Deploy — a permanent free public URL

The task can be demoed with a local tunnel (`cloudflared` / `ngrok` / `localtunnel`), but a
deploy gives a stable URL that survives your laptop being closed — good for a presentation
and for graders. As of late 2026 Render, Fly and Hugging Face Docker Spaces all require a card (they do not charge on the free plan, but a card is needed to verify). The genuinely card-free path is a local tunnel — see [RUNBOOK.md](RUNBOOK.md). Deploy only if you want a permanent URL and can add a card.

The repo already contains a `Dockerfile` (portable) and `render.yaml` (Render blueprint).
Secrets are **never committed** — you enter them in the host's dashboard.

## Environment variables to set on the host

| var | value |
|---|---|
| `SERVICENOW_INSTANCE_URL` | `https://dev434590.service-now.com` |
| `SERVICENOW_USERNAME` | `admin` |
| `SERVICENOW_PASSWORD` | (your PDI password) |
| `GEMINI_API_KEY` | (your AI Studio key) |
| `WEBHOOK_SHARED_SECRET` | any string; must match the Business Rule header |
| `SERVICENOW_CLOSE_CODE` | `Solution provided` |
| `GEMINI_MODEL` | `gemini-flash-latest` |
| `SERVICENOW_WRITEBACK` | `on` |

## Option A — Render (easiest; needs the repo on GitHub)

1. Push the repo to GitHub.
2. <https://dashboard.render.com> → **New** → **Blueprint** → pick the repo. Render reads
   `render.yaml`, creates the service.
3. It prompts for the `sync: false` vars — paste the secrets from the table.
4. Wait for the build. Your URL is `https://task0-agentic-incident-flow.onrender.com`
   (or similar). Health check: `/healthz`.
5. In the ServiceNow Business Rule, set `setEndpoint('https://<your-service>.onrender.com/webhook')`.

> Free plan spins the service down after ~15 min idle; the next request takes ~50 s to wake
> it. For a demo, hit `/healthz` once first to warm it.

## Option B — Hugging Face Spaces (no GitHub push needed)

1. <https://huggingface.co> → **New Space** → SDK **Docker** → **Blank**.
2. In the Space **Settings → Variables and secrets**, add the vars from the table (use
   *Secrets* for the credentials).
3. Push this repo to the Space's git remote (HF gives you the URL), or upload the files.
   HF builds the `Dockerfile`. HF injects `PORT` (usually 7860 — the Dockerfile handles it).
4. URL: `https://<user>-<space>.hf.space`. Point the Business Rule at `/webhook` there.

> Spaces sleep after ~48 h idle — much more forgiving than Render.

## Option C — Koyeb (no card, no aggressive sleep)

1. <https://app.koyeb.com> → **Create Service** → **Docker** (or GitHub).
2. Add the env vars from the table.
3. Deploy. URL: `https://<app>-<org>.koyeb.app`.

## After deploy — verify

```bash
curl https://<your-url>/healthz            # -> {"status":"ok"}
# then create an incident in the PDI and watch it get processed
```
