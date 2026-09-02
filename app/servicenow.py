"""Write the decision back onto the same incident via the ServiceNow Table API (FR4).

    respond  -> resolve: work_notes + close_notes + close_code + state 6
    ask      -> comments (customer-visible clarifying question)
    escalate -> work_notes ("Escalated to a human: ...")

Basic auth (allowed for this task). Transient failures (network, 5xx) are retried with
backoff; a 4xx is surfaced immediately as WritebackError (it will not get better on retry).
"""

import logging

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from app.config import get_settings
from app.decision import Decision, DecisionType

log = logging.getLogger("task0.servicenow")


class WritebackError(RuntimeError):
    """Raised when the incident could not be updated."""


def build_body(decision: Decision) -> dict[str, str]:
    """The PATCH body for a decision. Journal fields (work_notes, comments) append."""
    if decision.decision is DecisionType.respond:
        return {
            "work_notes": decision.message,
            "close_notes": decision.message,
            "close_code": get_settings().servicenow_close_code,
            "state": "6",  # Resolved
        }
    if decision.decision is DecisionType.ask:
        return {"comments": decision.message}
    return {"work_notes": f"Escalated to a human: {decision.message}"}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=20),
    reraise=True,
)
def _patch(sys_id: str, body: dict[str, str]) -> dict:
    s = get_settings()
    resp = httpx.patch(
        f"{s.servicenow_base}/api/now/table/incident/{sys_id}",
        json=body,
        auth=(s.servicenow_username, s.servicenow_password),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def write_back(incident_sys_id: str, number: str, decision: Decision) -> None:
    """Apply the decision to the incident. Raises WritebackError on failure."""
    body = build_body(decision)
    try:
        _patch(incident_sys_id, body)
    except httpx.HTTPStatusError as exc:
        raise WritebackError(
            f"ServiceNow rejected the update ({exc.response.status_code}): "
            f"{exc.response.text[:300]}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - re-wrapped for the caller
        raise WritebackError(f"ServiceNow write-back failed: {exc}") from exc
    log.info(
        "wrote back",
        extra={
            "incident": number,
            "decision": decision.decision.value,
            "fields": sorted(body),
        },
    )
