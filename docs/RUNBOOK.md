# Runbook — run the live loop yourself (demo + screenshots)

Confirmed working on your setup: `gemini-flash-latest` + `localtunnel` + PDI `dev434590`.
`cloudflared`/`ngrok` are blocked by your current network — use `localtunnel` (or record
from a phone hotspot, where `cloudflared tunnel --url http://localhost:8000` also works).

---

## 0. One-time check

`.env` already has everything. Confirm these lines:

```
GEMINI_MODEL=gemini-flash-latest
SERVICENOW_WRITEBACK=on
WEBHOOK_SHARED_SECRET=task0-secret-2026
SERVICENOW_CLOSE_CODE="Solution provided"
```

## 1. Start the service — Terminal 1

```bash
cd ~/Desktop/Sprints-0-Task
uv run uvicorn app.main:app --port 8000
```

Leave it running. This window shows the JSON logs you'll point the camera at.

## 2. Start the tunnel — Terminal 2

```bash
npx localtunnel --port 8000
```

Copy the `https://<name>.loca.lt` URL it prints. **If it drops, Ctrl-C and re-run** — the
URL changes, so redo step 3.

## 3. Point the Business Rule at the tunnel — browser

ServiceNow → **All** → type `sys_script.list` → open **`Task0 - Send Incident to Agent`**:

- **Active** = ✅ true
- In the **Script**, change the endpoint line to your tunnel URL, keeping `/webhook`:
  `r.setEndpoint('https://<name>.loca.lt/webhook');`
- Confirm this line matches your `.env`:
  `r.setRequestHeader('X-Webhook-Secret', 'task0-secret-2026');`
- **Update** (save).

## 4. Smoke test

Create one incident (**All → Incident → New**, any Short description, **Submit**). Within
~15 s Terminal 1 logs `accepted → decision made → wrote back`, and the incident shows the
result. If nothing happens: check the tunnel is still up (step 2) and the URL in the rule
matches; check ServiceNow **All → System Log → All**, filter `Task0`.

---

## 5. The 7 screenshots

**Shot 1 — the Business Rule.** Screenshot the `Task0 - Send Incident to Agent` form
(Name, Table = Incident, When = after, Insert ✅, the Advanced script visible).

**Shots 2–7 — before/after for each decision.** Cleanest method:

1. In `.env` set `SERVICENOW_WRITEBACK=off`, restart Terminal 1. Business Rule still on.
2. Create these three incidents:
   | Short description | Description |
   |---|---|
   | `Printer not printing after office move` | `It was working yesterday. I tried turning it off and on.` |
   | `Cannot send email` | `It just doesn't work.` |
   | `Request: annual leave approval` | `I would like to take next week off.` |
   Terminal 1 logs the decision (`respond` / `ask` / `escalate`) but writes nothing.
   **Screenshot each incident now — these are the 3 "before" shots.** Note each
   incident number.
3. In `.env` set `SERVICENOW_WRITEBACK=on`, restart Terminal 1.
4. For each of the three, drive the write-back onto it (Terminal 3):
   ```bash
   cd ~/Desktop/Sprints-0-Task
   uv run python scripts/send_test.py \
     --url https://<name>.loca.lt/webhook --secret task0-secret-2026 --force \
     --sys-id <SYS_ID> --number <INC number> \
     --short "Printer not printing after office move" \
     --description "It was working yesterday. I tried turning it off and on."
   ```
   (`--sys-id` is in the incident's URL or the form; repeat with the email + leave text.)
5. Refresh each incident — **screenshot the 3 "after" shots**:
   - printer → **Resolved**, Resolution code `Solution provided`, resolution/work notes = the fix
   - email → **Additional comments** has a clarifying question
   - leave → a **work note** "Escalated to a human: …"

Put the 7 images in `docs/screenshots/`.

---

## 6. Demo video (2–4 min) — shot list

1. **(20s)** Terminal 1 (`uvicorn …`) and Terminal 2 (`localtunnel …`) running; say what the service does.
2. **(15s)** The Business Rule in ServiceNow (active, endpoint = your tunnel URL).
3. **(40s) respond** — create the printer incident → **Submit**. Cut to Terminal 1:
   `accepted → decision made decision=respond → wrote back`. Refresh the incident →
   **Resolved** with the fix.
4. **(25s) ask** — create "Cannot send email / It just doesn't work." → log `decision=ask`
   → the incident's **Additional comments** shows a clarifying question.
5. **(25s) escalate** — create the annual-leave incident → log `decision=escalate` → a
   **work note** on the incident.
6. **(20s) no double-processing** — this is a **double POST of one payload**, not two
   tickets:
   ```bash
   uv run python scripts/send_test.py --url https://<name>.loca.lt/webhook \
     --secret task0-secret-2026 --sys-id <SYS_ID> --number <INC> --short "test"
   # run it twice
   ```
   First → `{"status":"accepted"}`; second → `{"status":"duplicate"}`; incident updated once.
7. **(15s) bad input** —
   ```bash
   curl -s -XPOST https://<name>.loca.lt/webhook \
     -H 'content-type: application/json' -H 'X-Webhook-Secret: task0-secret-2026' -d '{"number":"x"}'
   ```
   → clean `422`; the service is still serving `/healthz`.

---

## Notes

- **Gemini quota:** ~20 requests/day *per model id*. Keep the whole session under ~15
  incidents and don't create them faster than one per ~8 s. If `gemini-flash-latest` runs
  out, set `GEMINI_MODEL=gemini-2.5-flash` (separate bucket) or use a second API key.
- **localtunnel first visit in a browser** shows a "click to continue" page (it wants your
  public IP, which it displays). ServiceNow's calls skip it via the `bypass-tunnel-reminder`
  header already in the rule.
- When done: set the Business Rule **Active = false** so it doesn't fire at a dead URL later.
