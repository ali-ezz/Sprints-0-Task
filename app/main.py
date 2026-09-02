"""FastAPI service.

POST /webhook  — validate the incident payload, reply 202 immediately, and run the
                Gemini decision + ServiceNow write-back in a background task.
GET  /healthz  — liveness probe.

Design guarantees:
* The endpoint replies in well under NFR1's ~2 s: the only synchronous work is payload
  validation and the atomic dedup claim.
* The service never returns a bare 500 for a bad payload — a RequestValidationError
  becomes a clean 422, and a catch-all handler backstops everything else (NFR3).
* The background task never raises (its failures are logged, not crashed).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.decision import decide
from app.idempotency import get_idempotency
from app.logs import configure_logging
from app.models import IncidentPayload

log = logging.getLogger("task0.webhook")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    get_settings()  # fail fast if a required env var is missing
    log.info("service started")
    yield


app = FastAPI(title="Task 0 - Agentic Incident Flow", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def _on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "invalid webhook payload", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def _on_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "internal error"})


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


def process_incident(payload: IncidentPayload) -> None:
    """Background work: decide, then (Phase 6) write back. Must never raise."""
    settings = get_settings()
    try:
        result = decide(payload.short_description, payload.description, payload.priority)
        log.info(
            "decision made",
            extra={"incident": payload.number, "decision": result.decision.value},
        )
        # Phase 6 wires the ServiceNow write-back here; complete() will move to
        # *after* a successful PATCH so an incident is only marked done once written.
        if settings.writeback_enabled:
            get_idempotency().complete(payload.incident_sys_id, result.decision.value)
    except Exception:
        log.exception("background processing failed", extra={"incident": payload.number})
        if settings.writeback_enabled:
            get_idempotency().fail(payload.incident_sys_id)


@app.post("/webhook", status_code=202, response_model=None)
async def webhook(
    payload: IncidentPayload,
    background: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> JSONResponse | dict:
    settings = get_settings()
    if settings.webhook_shared_secret and x_webhook_secret != settings.webhook_shared_secret:
        log.warning("rejected webhook: bad shared secret", extra={"incident": payload.number})
        return JSONResponse(status_code=401, content={"error": "bad or missing X-Webhook-Secret"})

    # Dedup claim (synchronous, atomic, before 202). Skipped in dry-run so the same
    # incident can be replayed for before/after screenshots.
    if settings.writeback_enabled and not get_idempotency().claim(
        payload.incident_sys_id, payload.number
    ):
        log.info("duplicate, skipping", extra={"incident": payload.number})
        return {"status": "duplicate", "incident": payload.number}

    background.add_task(process_incident, payload)
    log.info("accepted", extra={"incident": payload.number})
    return {"status": "accepted", "incident": payload.number}
