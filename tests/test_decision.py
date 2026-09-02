import httpx
import pytest
from google.genai import errors as genai_errors

from app import decision as dec
from app.decision import ESCALATE_FALLBACK, Decision, DecisionType, decide


# ---- _parse -----------------------------------------------------------------
def test_parse_valid_respond():
    d = dec._parse('{"decision": "respond", "message": "Restart the printer."}')
    assert d.decision is DecisionType.respond
    assert d.message == "Restart the printer."


@pytest.mark.parametrize("value", ["ask", "escalate"])
def test_parse_valid_other(value):
    assert dec._parse(f'{{"decision": "{value}", "message": "text"}}').decision.value == value


def test_parse_out_of_enum_value_escalates():
    assert dec._parse('{"decision": "banana", "message": "x"}') == ESCALATE_FALLBACK


def test_parse_garbage_escalates():
    assert dec._parse("not json at all") == ESCALATE_FALLBACK


def test_parse_empty_message_escalates():
    assert dec._parse('{"decision": "respond", "message": "   "}') == ESCALATE_FALLBACK


# ---- decide() never raises ------------------------------------------------
def test_decide_happy_path(monkeypatch):
    monkeypatch.setattr(
        dec, "_call_gemini", lambda *a, **k: '{"decision": "ask", "message": "Which app?"}'
    )
    d = decide("Cannot send email", "It just doesn't work.", 3)
    assert d.decision is DecisionType.ask and d.message == "Which app?"


def test_decide_swallows_exceptions(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(dec, "_call_gemini", boom)
    assert decide("x", "y", 1) == ESCALATE_FALLBACK


def test_decide_swallows_api_error(monkeypatch):
    def boom(*a, **k):
        raise genai_errors.ClientError(400, {"error": {"message": "bad"}})

    monkeypatch.setattr(dec, "_call_gemini", boom)
    assert decide("x", "y", 1) == ESCALATE_FALLBACK


# ---- retry classification ------------------------------------------------
def test_is_retryable_server_error():
    assert dec._is_retryable(genai_errors.ServerError(503, {"error": {"message": "busy"}}))


def test_is_retryable_429():
    assert dec._is_retryable(genai_errors.ClientError(429, {"error": {"message": "quota"}}))


def test_not_retryable_400():
    assert not dec._is_retryable(genai_errors.ClientError(400, {"error": {"message": "bad"}}))


def test_is_retryable_network():
    assert dec._is_retryable(httpx.ConnectError("no route"))


def test_fallback_is_a_valid_decision():
    assert isinstance(ESCALATE_FALLBACK, Decision)
    assert ESCALATE_FALLBACK.decision is DecisionType.escalate
