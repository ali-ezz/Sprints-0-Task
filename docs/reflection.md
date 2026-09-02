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

**The friction was operational, not conceptual.** The ServiceNow PDI rejected Basic auth
even after two password resets — probably an account lockout from my own repeated probe
attempts — which blocked live write-back testing. And the Gemini free tier turned out to
allow only ~20–50 requests per *day* on `gemini-2.5-flash`, far below the per-minute
number everyone quotes, so I had to ration real calls and lean on mocked unit tests plus a
small throttled eval script. Both pushed me to build the whole service against mocks first
and verify the decision quality with a handful of real calls rather than a big sweep.

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
  and any custom mandatory fields differ by instance; the code assumes the stock
  `Solved (Permanently)` and would need a quick check on a real instance.
- **Observability.** Structured logs with the incident number as a correlation id are a
  start; request tracing and a `/metrics` endpoint would make failures faster to diagnose.
