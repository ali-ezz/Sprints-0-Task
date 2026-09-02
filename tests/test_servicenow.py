import json

import httpx
import pytest
import respx

from app.decision import Decision, DecisionType
from app.servicenow import WritebackError, _patch, build_body, write_back

BASE = "https://dev-test.service-now.com"
URL = f"{BASE}/api/now/table/incident/sys1"


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Don't actually sleep between tenacity retries during tests."""
    monkeypatch.setattr(_patch.retry, "sleep", lambda _seconds: None)


def _d(kind: str, msg: str = "text") -> Decision:
    return Decision(decision=DecisionType(kind), message=msg)


# ---- body construction -----------------------------------------------------
def test_body_respond_resolves():
    body = build_body(_d("respond", "Restart the printer."))
    assert body == {
        "work_notes": "Restart the printer.",
        "close_notes": "Restart the printer.",
        "close_code": "Solved (Permanently)",
        "state": "6",
    }


def test_body_ask_is_customer_comment():
    assert build_body(_d("ask", "Which email client?")) == {"comments": "Which email client?"}


def test_body_escalate_is_work_note_with_prefix():
    assert build_body(_d("escalate", "HR request")) == {
        "work_notes": "Escalated to a human: HR request"
    }


# ---- write_back ----------------------------------------------------------
@respx.mock
def test_write_back_respond_patches_correctly():
    route = respx.patch(URL).mock(return_value=httpx.Response(200, json={"result": {}}))
    write_back("sys1", "INC1", _d("respond", "Do the thing"))
    assert route.called
    req = route.calls.last.request
    assert req.headers["authorization"].startswith("Basic ")
    assert json.loads(req.content)["state"] == "6"


@respx.mock
def test_write_back_4xx_raises_without_retry():
    route = respx.patch(URL).mock(return_value=httpx.Response(403, text="No"))
    with pytest.raises(WritebackError):
        write_back("sys1", "INC1", _d("ask"))
    assert route.call_count == 1  # not retried


@respx.mock
def test_write_back_5xx_retries_then_raises():
    route = respx.patch(URL).mock(return_value=httpx.Response(503, text="busy"))
    with pytest.raises(WritebackError):
        write_back("sys1", "INC1", _d("escalate"))
    assert route.call_count == 4  # stop_after_attempt(4)


@respx.mock
def test_write_back_recovers_after_one_5xx():
    route = respx.patch(URL).mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"result": {}})]
    )
    write_back("sys1", "INC1", _d("respond", "ok"))
    assert route.call_count == 2
