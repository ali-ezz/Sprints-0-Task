# ServiceNow setup (FR1)

You do not need prior ServiceNow experience. ~15 minutes.

## 1. Get a free PDI

1. Sign up at <https://developer.servicenow.com> → **Request Instance** (latest release).
2. After a few minutes you get an instance URL (`https://devXXXXXX.service-now.com`) and
   an `admin` password (portal → **Manage instance password** → use the **Copy** button).
3. Put the URL + credentials in `.env` (`SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`,
   `SERVICENOW_PASSWORD`).

> A PDI hibernates after long inactivity; repeated failed logins can lock `admin` for
> ~30 min. If the REST API returns `401`, first confirm the password by logging into the
> web UI.

## 2. Start the service and a tunnel

```bash
uv run uvicorn app.main:app --port 8000
cloudflared tunnel --url http://localhost:8000     # copy the https://<id>.trycloudflare.com URL
```

The tunnel URL changes every restart — re-do step 4 whenever it does.

## 3. Optional: set a shared secret

Put the same value in `.env` (`WEBHOOK_SHARED_SECRET`) and in the Business Rule script
(`X-Webhook-Secret`). Leave both blank to disable the check.

## 4. Create the Business Rule

**All → Business Rules → New**

| Field | Value |
|---|---|
| Name | `Task0 - Send Incident to Agent` |
| Table | `Incident [incident]` |
| Advanced | checked |
| When | `after` |
| Insert | **checked** |
| Update / Delete / Query | **unchecked** |

> `Insert` only. If `Update` is also checked, our write-back PATCH re-fires the rule in a
> loop. (The dedup guard would stop the loop, but don't rely on it.)

**Advanced tab → Script:** paste [`../servicenow/business_rule.js`](../servicenow/business_rule.js)
and replace `YOUR-TUNNEL-URL` (keep `/webhook`) and `YOUR_SHARED_SECRET`. Submit.

## 5. Test

Create an incident (**All → Incident → Create New**), set a Short description, Submit.
Within a few seconds:

- the service logs `accepted` → `decision made` → `wrote back`;
- the incident shows the result — Resolved with a solution (`respond`), a customer-visible
  comment (`ask`), or a work note (`escalate`).

If nothing arrives: check the tunnel is up and the URL in the rule matches; check the PDI
**System Log → All** for `Task0` lines written by `gs.info` / `gs.error`.

## Decision → incident fields

| Decision | Fields written |
|---|---|
| `respond` | `work_notes`, `close_notes`, `close_code`, `state = 6` (Resolved) |
| `ask` | `comments` (customer-visible) |
| `escalate` | `work_notes` (`"Escalated to a human: …"`) |
