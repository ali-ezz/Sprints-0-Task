# Demo video and screenshots

> The loop is already verified working on `dev434590` (see the repo README). Incidents
> `INC0010012` (respond), `INC0010013` (ask), `INC0010014` (escalate) are the reference
> results from that run. What's below is for capturing your own clean before/after set and
> the video.

## Gemini free-tier quota — plan around it

`gemini-2.5-flash` free tier allows **~20 `generateContent` requests per day per project**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) plus ~10/min. When it's exhausted,
every decision falls back to `escalate` (by design — safe), which is not what you want on
camera. Options:

- Wait for the daily reset (~24 h cycle, midnight US Pacific), then record in one sitting.
- Or create a **second API key in a new Google AI Studio project** (fresh 20/day) and put
  it in `.env`.
- Keep the whole demo under ~10 incidents and don't create them faster than one every
  ~8 seconds.

## Tunnel — pick what works on your network

- **ngrok** — most reliable. One-time: grab your real authtoken from the ngrok dashboard
  ("Your Authtoken" — the long string, not the `cr_…` id) → `ngrok config add-authtoken <TOKEN>`
  → `ngrok http 8000`.
- **cloudflared** — `cloudflared tunnel --url http://localhost:8000`. Free, no account,
  but some networks/DNS block `*.trycloudflare.com` (this one did — check with
  `nslookup test.trycloudflare.com`).
- **localtunnel** — `npx localtunnel --port 8000`. No account, but the free `loca.lt`
  server is flaky (drops often).

The tunnel URL changes every restart → update the Business Rule's `setEndpoint(...)` each time.

## Before you start

1. **Verify `close_code` values on your instance** (the `respond` write-back sets one):
   ```bash
   curl -s -u "admin:$SERVICENOW_PASSWORD" \
     "$SERVICENOW_INSTANCE_URL/api/now/table/sys_choice?sysparm_query=name=incident^element=close_code^language=en&sysparm_fields=value,label" \
     | python3 -m json.tool
   ```
   Put a value from that list in `.env` as `SERVICENOW_CLOSE_CODE` (default
   `Solution provided`, valid on `dev434590`; older instances differ).
2. If the REST API 401s while browser login works: add the `snc_basic_auth_api_access`
   role to the user ([servicenow_setup.md](servicenow_setup.md)).
3. Start the service + tunnel, create the Business Rule
   ([servicenow_setup.md](servicenow_setup.md)).
4. Optional: `GEMINI_MODEL=gemini-2.5-flash-lite` if you're near the daily quota. If you
   switch, first run `uv run python scripts/eval_prompt.py --model gemini-2.5-flash-lite --n 3`
   and confirm all three goldens still pass.

## The 7 screenshots

1. **Business Rule** — the form: Name, Table `Incident`, When `after`, `Insert` checked
   (Update unchecked), Advanced script visible.

Then **before / after** for each decision. Clean method (avoids racing the ~5 s
processing window):

1. Run the service with `SERVICENOW_WRITEBACK=off`.
2. Create three incidents in the PDI:
   - "Printer not printing after office move" / "It was working yesterday. I tried turning it off and on." → **respond**
   - "Cannot send email" / "It just doesn't work." → **ask**
   - "Request: annual leave approval" / "I would like to take next week off." → **escalate**
   The Business Rule fires; the service logs the decision but writes nothing. Screenshot
   each incident now — these are the **before** shots. Note each `incident_sys_id`
   (service log line, or the URL / `sys_id` on the form).
3. Restart the service with `SERVICENOW_WRITEBACK=on`.
4. For each incident, drive the write-back onto it:
   ```bash
   uv run python scripts/send_test.py --url https://<tunnel>/webhook --secret "$WEBHOOK_SHARED_SECRET" \
     --sys-id <SYS_ID> --number <INC number> \
     --short "<the short description>" --description "<the details>" --force
   ```
5. Refresh each incident and screenshot — the **after** shots:
   - respond → **Resolved**, with the solution in Resolution notes / work notes
   - ask → **Additional comments** shows the clarifying question
   - escalate → a work note "Escalated to a human: …"

## Demo video (2–4 min) — shot list

1. **Repo + start** (~20 s) — `uv sync`, `uvicorn …`, `cloudflared …`; show the tunnel URL.
2. **Business Rule** (~15 s) — the config, and the script with the tunnel URL pasted in.
3. **respond** (~40 s) — create the printer incident → Submit. Cut to the service log:
   `accepted` → `decision made decision=respond` → `wrote back`. Refresh the incident →
   Resolved with the KB-1 fix.
4. **ask** (~25 s) — create "Cannot send email / it just doesn't work" → log shows
   `decision=ask` → incident's Additional comments has a clarifying question.
5. **escalate** (~25 s) — create the annual-leave incident → `decision=escalate` → work
   note on the incident.
6. **No double processing** (~20 s) — this is **not** two tickets (each new ticket has its
   own `sys_id`). Send the *same payload twice*:
   ```bash
   uv run python scripts/send_test.py --sys-id <SYS_ID> --number <INC> --short "…" --url https://<tunnel>/webhook
   uv run python scripts/send_test.py --sys-id <SYS_ID> --number <INC> --short "…" --url https://<tunnel>/webhook
   ```
   First → `{"status":"accepted"}`; second → `{"status":"duplicate"}`; the incident is
   updated once.
7. **Bad input** (~15 s) — `curl -s -XPOST https://<tunnel>/webhook -H 'content-type: application/json' -d '{"number":"x"}'`
   → clean `422`, service still serving `/healthz`.
