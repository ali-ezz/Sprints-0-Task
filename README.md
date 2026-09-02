# Task 0 — Agentic Incident Flow

A support ticket is created in ServiceNow; this service decides what to do with it and
writes the answer back onto the same ticket — automatically, with no manual steps.

```
Incident created (ServiceNow PDI)
        │  Business Rule (after + Insert)
        ▼
POST /webhook  ──►  validate  ──►  dedupe (SQLite)  ──►  202 Accepted   (< 2 s)
                                                             │  background
                                                             ▼
                                   render prompt.txt + 5 KB articles  ──►  Gemini
                                   → {"decision": "respond|ask|escalate", "message": "..."}
                                                             │
                                                             ▼
                        PATCH /api/now/table/incident/{sys_id}   (ServiceNow REST, Basic auth)
                        respond → resolve   |   ask → customer comment   |   escalate → work note
```

## Requirements

- **Python 3.11+** (this repo pins 3.11). On macOS the system `python3` may be 3.9 — use
  `uv` or an explicit `python3.11`.
- [`uv`](https://docs.astral.sh/uv/) (recommended) **or** `pip` + `venv`.
- A public tunnel to `localhost:8000`: [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
  (recommended) or [`ngrok`](https://ngrok.com/).
- A free **Gemini API key** — <https://aistudio.google.com>.
- A free **ServiceNow PDI** — <https://developer.servicenow.com>.

## Setup

```bash
git clone https://github.com/ali-ezz/Sprints-0-Task.git
cd Sprints-0-Task

# with uv (recommended)
uv sync

# or with pip
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# configure
cp .env.example .env
# then edit .env — see the table below
```

### `.env`

| Variable | Meaning |
|---|---|
| `SERVICENOW_INSTANCE_URL` | e.g. `https://devXXXXXX.service-now.com` (no trailing slash) |
| `SERVICENOW_USERNAME` / `SERVICENOW_PASSWORD` | PDI `admin` credentials (Basic auth) |
| `SERVICENOW_CLOSE_CODE` | close code used when resolving on `respond` (default `Solved (Permanently)`) |
| `GEMINI_API_KEY` | from Google AI Studio |
| `GEMINI_MODEL` | default `gemini-2.5-flash` (`gemini-2.5-flash-lite` has a higher daily quota) |
| `PORT` | default `8000` |
| `WEBHOOK_SHARED_SECRET` | optional; if set, the Business Rule must send it as `X-Webhook-Secret` |
| `SERVICENOW_WRITEBACK` | `on` (default) or `off` to compute + log the decision without writing back |
| `DEDUP_DB_PATH` | SQLite file for the once-only guard (default `dedup.sqlite3`) |

Full ServiceNow / Business Rule walkthrough: [`docs/servicenow_setup.md`](docs/servicenow_setup.md).
Demo + screenshot guide: [`docs/demo_and_screenshots.md`](docs/demo_and_screenshots.md).

## Run

```bash
# 1. start the service
uv run uvicorn app.main:app --port 8000          # (add --reload only for local dev)

# 2. expose it
cloudflared tunnel --url http://localhost:8000   # copy the https://<...>.trycloudflare.com URL
# or: ngrok http 8000

# 3. in ServiceNow, paste that URL + /webhook into the Business Rule
#    (see servicenow/business_rule.js and docs/ for the full setup)
```

Create an incident on the PDI → within seconds the decision appears on that incident.

## Test

```bash
uv run pytest -q                       # unit tests (ServiceNow + Gemini mocked)
uv run python scripts/send_test.py     # POST the 3 golden payloads to a running service
uv run python scripts/eval_prompt.py   # run the 3 goldens through the real model N times
```

## Layout

| Path | What |
|---|---|
| `app/` | the service (`main.py`, `decision.py`, `servicenow.py`, `idempotency.py`, …) |
| `prompt.txt` | the exact prompt template the service sends to Gemini |
| `app/data/kb_articles.json` | the 5 knowledge articles (vendored from the asset pack) |
| `servicenow/business_rule.js` | the Business Rule to paste into the PDI |
| `scripts/` | offline harness + prompt eval |
| `tests/` | unit tests + vendored `test_incidents.json` |
| `docs/` | Business Rule setup, screenshots, reflection |

## Troubleshooting

- **Nothing hits the service** — the tunnel URL changes every restart; update the Business
  Rule. Check the PDI **System Log → All** for `Task0` lines.
- **PDI asleep** — wake it from the developer portal.
- **`429` / `503` from Gemini** — free-tier limits are ~10 req/min and, on a fresh
  project, as low as ~20–50 req/**day** for `gemini-2.5-flash`. The service retries with
  backoff and falls back to `escalate` when exhausted. For heavy iteration set
  `GEMINI_MODEL=gemini-2.5-flash-lite` (higher daily quota) or wait for the daily reset.
- **PDI login fails** — repeated failed Basic-auth attempts can lock the account for ~30
  min; confirm the password by logging into the ServiceNow UI first.
- **Incident stuck / not re-processed** — a completed incident is deduped by
  `incident_sys_id`; delete its row from `dedup.sqlite3` (or use
  `scripts/send_test.py --force` for the synthetic ones) to replay it.
