# Reflection & Live Verification

## Live Verification: The Three Test Tickets (FR1–FR6)

The entire loop was verified live against ServiceNow Personal Developer Instance (PDI) `dev434590` (Australia release) using `gemini-flash-latest` and public tunnel connectivity.

Each newly submitted ticket triggered ServiceNow Business Rule **`Task0 - Send Incident to Agent`** (`after` + `Insert` only), sent an HTTP POST to `/webhook`, received an immediate HTTP `202 Accepted`, and completed end-to-end write-back asynchronously via the ServiceNow Table API.

### Verification Summary Table

| Incident Number | `sys_id` | Scenario & Input | Expected Decision | Actual Decision & Matched KB | ServiceNow PDI Write-Back State & Fields | Turnaround Time | Screenshot Evidence |
|---|---|---|---|---|---|---|---|
| **INC0010012** | `1c0aabf2734703502aedfed25ab8b74b` | "Printer not printing after office move"<br>_"It was working yesterday. I tried turning it off and on."_ | `respond` | **`respond`**<br>(KB0010001: Printer Troubleshooting) | **State**: `6` (Resolved)<br>**Close Code**: `Solution provided`<br>**Close Notes**: `"Restart the printer and unplug the cable for 30 seconds."`<br>**Work Notes**: Populated with solution | Created: 15:30:07<br>Resolved: 15:30:16<br>(**~9 s** total pipeline) | [Before](screenshots/02-printer-before.png)<br>[After](screenshots/03-printer-after.png) |
| **INC0010013** | `6b0ca37a734703502aedfed25ab8b75a` | "Cannot send email"<br>_"It just doesn't work."_ | `ask` | **`ask`**<br>(KB0010002 exists, but ticket is too vague for concrete fix) | **State**: `1` (New — remains open)<br>**Additional Comments (Customer visible)**:<br>_"Could you provide any specific error messages you receive when attempting to send an email, or confirm what email client you are using?"_ | Created: 15:37:38<br>Updated: 15:37:44<br>(**~6 s** total pipeline) | [Before](screenshots/04-email-before.png)<br>[After](screenshots/05-email-after.png) |
| **INC0010014** | `a04d2b3e734703502aedfed25ab8b7a0` | "Request: annual leave approval"<br>_"I would like to take next week off."_ | `escalate` | **`escalate`**<br>(Zero KB match — HR policy request out of IT scope) | **State**: `1` (New — human triage queue)<br>**Work Notes (Internal only)**:<br>_"Escalated to a human: This is an HR leave request not covered by IT support knowledge base articles, so human review is required."_<br>**Comments**: Untouched | Created: 15:41:53<br>Updated: 15:41:58<br>(**~5 s** total pipeline) | [Before](screenshots/06-leave-before.png)<br>[After](screenshots/07-leave-after.png) |

---

### Detailed Test Ticket Verification

#### 1. Ticket 1 (`respond`): Printer Issue (`INC0010012`)
- **Input**: User reported a printer failure following an office move, mentioning it worked yesterday and basic power-cycling was attempted.
- **Decision Engine**: Correctly recognized specific symptoms matching KB Article KB0010001 (unplugging cables / clearing paper jams).
- **ServiceNow Table API Write-Back**:
  - `state` updated to `6` (Resolved).
  - `close_code` set to `"Solution provided"` (validated against instance choice values).
  - `close_notes` and `work_notes` populated with the actionable fix.
- **Evidence**: Visual proof in [02-printer-before.png](screenshots/02-printer-before.png) showing New state and blank notes, and [03-printer-after.png](screenshots/03-printer-after.png) showing Resolved state, close code, and journal entries.

#### 2. Ticket 2 (`ask`): Vague Email Issue (`INC0010013`)
- **Input**: User reported "Cannot send email" with details "It just doesn't work."
- **Decision Engine**: While KB Article KB0010002 covers email errors, the symptom is too vague to determine whether it is an authentication, attachment, or network issue. The prompt correctly classified this as `ask` instead of guessing.
- **ServiceNow Table API Write-Back**:
  - `state` remains `1` (New), awaiting end-user input.
  - Customer-visible `comments` field received: *"Could you provide any specific error messages you receive when attempting to send an email, or confirm what email client you are using?"*
  - Internal `work_notes` left clean to ensure the user receives immediate notification.
- **Evidence**: [04-email-before.png](screenshots/04-email-before.png) vs [05-email-after.png](screenshots/05-email-after.png).

#### 3. Ticket 3 (`escalate`): HR Leave Approval (`INC0010014`)
- **Input**: User submitted an annual leave approval request.
- **Decision Engine**: Evaluated all 5 IT knowledge articles; none cover vacation or leave approval. The engine correctly flagged it for human routing.
- **ServiceNow Table API Write-Back**:
  - `state` remains `1` (New).
  - Appended an internal work note: *"Escalated to a human: This is an HR leave request not covered by IT support knowledge base articles, so human review is required."*
  - Customer-visible `comments` was NOT touched, preventing confusion for the employee.
- **Evidence**: [06-leave-before.png](screenshots/06-leave-before.png) vs [07-leave-after.png](screenshots/07-leave-after.png).

---

## Evidence of Fast Webhook Response Time (NFR1)

Non-Functional Requirement 1 (NFR1) dictates that the webhook must respond in **under 2 seconds** so ServiceNow's Business Rule thread is not blocked by external LLM inference or network round-trips.

### Architecture & Decoupling

The webhook achieves ultra-fast response times by strictly separating **synchronous admission** from **asynchronous background execution**:

```
ServiceNow Business Rule
       │
       ▼  HTTP POST /webhook
┌─────────────────────────────────────────────────────────────┐
│ Synchronous Admission Handler (FastAPI)                     │
│ 1. Validate X-Webhook-Secret header                  <0.1 ms│
│ 2. Pydantic schema validation (IncidentPayload)      ~0.5 ms│
│ 3. Atomic SQLite idempotency claim (dedup.sqlite3)   ~0.8 ms│
│ 4. Register background worker & return HTTP 202      ~0.5 ms│
└─────────────────────────────────────────────────────────────┘
       │
       ▼  HTTP 202 Accepted (Synchronous return in ~1–9 ms)
ServiceNow Business Rule unblocks immediately (< 2.0 s SLA met)
       │
       ▼  Background Worker (Async via BackgroundTasks)
┌─────────────────────────────────────────────────────────────┐
│ 5. Render prompt.txt + 5 KB articles                 ~0.1 ms│
│ 6. Call Google Gemini API (gemini-flash-latest)     ~1.5–2.5s│
│ 7. Parse structured JSON {decision, message}         ~0.1 ms│
│ 8. PATCH /api/now/table/incident/{sys_id}           ~0.5–1.2s│
│ 9. Mark status 'done' in SQLite dedup database       ~0.8 ms│
└─────────────────────────────────────────────────────────────┘
```

### Measured Benchmark Data

Synchronous latency measured over live HTTP requests to the webhook:

| Metric | Measured Value | NFR1 SLA Target | Margin |
|---|---|---|---|
| **Minimum** | **0.60 ms** | < 2,000 ms | **3,333× under budget** |
| **Median** | **0.97 ms** | < 2,000 ms | **2,061× under budget** |
| **Mean** | **1.87 ms** | < 2,000 ms | **1,069× under budget** |
| **Maximum (p100)** | **9.07 ms** | < 2,000 ms | **220× under budget** |

Even under cold-start or initial connection setup, the synchronous response completes in under **10 milliseconds**, well over two orders of magnitude faster than the required 2-second SLA.

---

## Idempotency & Duplicate Payload Verification (FR5)

To prevent duplicate webhook deliveries from triggering multiple LLM evaluations or double-patching ServiceNow records:

1. **Admission Claim**: When `/webhook` receives a payload, it immediately executes an atomic SQL query against `dedup.sqlite3`:
   ```sql
   INSERT INTO processed_incidents (incident_sys_id, number, status, created_at, updated_at)
   VALUES (?, ?, 'processing', ?, ?)
   ON CONFLICT(incident_sys_id) DO UPDATE ...
   ```
2. **Double-Delivery Test**:
   - **Request 1**: Payload for `INC0010012` sent → SQLite returns claim granted → HTTP `202 Accepted` (`{"status": "accepted", "incident": "INC0010012"}`).
   - **Request 2** (identical payload resent): SQLite detects active or completed claim → returns claim denied → HTTP `202 Accepted` with payload `{"status": "duplicate", "incident": "INC0010012"}`. Background task is **not** scheduled.
   - Result: Incident is updated in ServiceNow exactly once, with zero duplicated work notes or status flaps.

---

## Negative Testing & Error Handling (NFR3)

The service enforces defensive validation at the perimeter:
- **Malformed JSON or Missing Fields**: Tested with `{}` and `{"number": "INC999"}` (missing required `short_description` and `incident_sys_id`). FastAPI returns a clean **HTTP 422 Unprocessable Entity** detailing validation errors; never an unhandled 500.
- **Unauthorized Calls**: When `WEBHOOK_SHARED_SECRET` is configured, requests lacking a valid `X-Webhook-Secret` header receive a clean **HTTP 401 Unauthorized**.
- **Service Continuity**: Health check probe at `/healthz` continuously returns `{"status": "ok"}` before, during, and after malformed request attempts.

---

## What was the hardest part?

**Getting `ask` vs `respond` right without gaming it.** Test ticket 2 ("Cannot send
email" / "It just doesn't work.") has to return `ask`, even though KB article 2 is
literally about email not sending. The naive prompt I started with ("you are a strict
classifier, answer from these articles") did the opposite of what I expected — it marked
the *clear* printer ticket as `ask`. Researching it, this is a known effect: simply
offering an "I'm not sure" option biases a model toward using it. The fix was to stop
treating `ask` as "ask when unsure" and make it a concrete test: does the ticket contain a
specific symptom and/or a step already tried? The printer ticket does ("was working
yesterday… tried turning it off and on"); the email ticket doesn't. That single
distinction is what the rubric in `prompt.txt` encodes.

The related decision was **keeping the three graded tickets out of the prompt.** Using
them as few-shot examples would make the test pass trivially and prove nothing about
generalisation, so the calibration examples in the prompt deliberately use *different*
scenarios (router, procurement, portal login) that exercise the other articles.

**The friction was operational, not conceptual**, and three live findings cost the most
time:

1. **ServiceNow Basic auth returned `401` with credentials that logged into the web UI
   fine.** The cause was ServiceNow's *Basic Authentication Account Security*: on recent
   releases the REST API rejects Basic auth unless the user holds the
   `snc_basic_auth_api_access` role. Adding that role to `admin` fixed it instantly. The
   same probe caught that this instance's valid `close_code` values are nothing like the
   `Solved (Permanently)` the docs imply — resolving needs `Solution provided` here, so
   that is the default in `config.py`.
2. **The Gemini free tier meters per *model id*, not per project.** `gemini-2.5-flash`
   allows only ~20 requests per *day* on a fresh key — far below the per-minute number
   that's usually quoted — and I exhausted it mid-testing. Switching `GEMINI_MODEL` to
   `gemini-flash-latest` gave a fresh daily bucket and unblocked the work, which is why
   that is now the default. It also pushed me to build the whole service against mocks
   and spend the real calls only on a small throttled eval plus the end-to-end runs.
3. **This network blocks `cloudflared` and `ngrok` inbound.** ServiceNow (calling from
   the cloud) reached both tunnels fine, but my own machine couldn't resolve or load the
   tunnel URL to verify it — so debugging felt like the loop was broken when it wasn't.
   `localtunnel` was the one that worked from here; a real deploy would remove the
   guesswork entirely.

## What would you improve with more time?

- **Durable background work.** `BackgroundTasks` plus the SQLite claim is enough for this
  task, but a real deployment should use a proper queue with a dead-letter path so a
  failed write-back is visibly retried rather than just marked `failed` in a local file.
- **A real evaluation set.** Three golden tickets is thin. I'd write ~30 varied tickets
  with expected labels and run an LLM-as-judge over the messages too, then tune the
  thinking budget and temperature against that instead of by feel.
- **A stable public URL.** The tunnel URL changing on every restart is the most likely
  thing to silently break the loop. A named Cloudflare tunnel or a small always-on deploy
  would remove that footgun (at the cost of the free-tier cold-start issues I wanted to
  avoid for the demo).
- **Per-instance verification of ServiceNow specifics** — the valid `close_code` values
  and any custom mandatory fields differ by instance. `SERVICENOW_CLOSE_CODE` is now
  configurable (default `Solution provided`, verified on this PDI), but a startup probe
  that lists the instance's real choice values would catch a mismatch before the first
  write-back instead of on it.
- **Observability.** Structured logs with the incident number as a correlation id are a
  start; request tracing and a `/metrics` endpoint would make failures faster to diagnose.

