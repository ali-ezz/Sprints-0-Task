# Reflection

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
