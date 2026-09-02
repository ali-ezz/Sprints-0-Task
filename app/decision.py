"""The decision step: ask Gemini for one of respond / ask / escalate, using only the KB.

Guarantees for callers:
* `decide()` never raises. Any failure (network, quota, unparseable output, empty message,
  out-of-enum value) resolves to a safe `escalate` decision — this is FR3's "if none of
  them fits, the decision is escalated" plus NFR3's "never crashes".
* The returned `decision` is always one of the three enum values (enforced by the schema
  the model is given and re-validated here).
"""

from __future__ import annotations

import logging
from enum import StrEnum

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from app.config import get_settings
from app.prompt import system_instruction, user_turn

log = logging.getLogger("task0.decision")


class DecisionType(StrEnum):
    respond = "respond"
    ask = "ask"
    escalate = "escalate"


class Decision(BaseModel):
    decision: DecisionType
    message: str


ESCALATE_FALLBACK = Decision(
    decision=DecisionType.escalate,
    message="Automated triage could not reach a reliable decision; routing to a human.",
)


def _is_retryable(exc: BaseException) -> bool:
    """Transient: 5xx from the API, 429 quota, or a transport-level network error."""
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) == 429:
        return True
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=20),
    reraise=True,
)
def _call_gemini(short_description: str, description: str, priority: int | None) -> str:
    s = get_settings()
    client = genai.Client(api_key=s.gemini_api_key)
    resp = client.models.generate_content(
        model=s.gemini_model,
        contents=user_turn(short_description, description, priority),
        config=types.GenerateContentConfig(
            system_instruction=system_instruction(),
            temperature=0,
            response_mime_type="application/json",
            response_schema=Decision,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            # We pass a Pydantic model as a response schema, not as a tool — turn off
            # automatic function calling so the SDK does not emit a spurious warning.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return resp.text or ""


def _parse(raw: str) -> Decision:
    try:
        parsed = Decision.model_validate_json(raw)
    except ValidationError:
        log.warning("gemini output not a valid Decision, escalating: %r", raw[:300])
        return ESCALATE_FALLBACK
    if not parsed.message.strip():
        log.warning("gemini returned empty message for %s, escalating", parsed.decision)
        return ESCALATE_FALLBACK
    return parsed


def decide(short_description: str, description: str, priority: int | None) -> Decision:
    """Classify one ticket. Never raises."""
    try:
        raw = _call_gemini(short_description, description, priority)
    except Exception:  # noqa: BLE001 — deliberately swallow everything (NFR3)
        log.exception("gemini call failed after retries, escalating")
        return ESCALATE_FALLBACK
    result = _parse(raw)
    log.info("decision=%s", result.decision.value)
    return result
