import pytest
from fastapi.testclient import TestClient

from app import main
from app.decision import Decision, DecisionType

GOOD = {
    "incident_sys_id": "abc123",
    "number": "INC0010001",
    "short_description": "Printer not printing after office move",
    "description": "It was working yesterday. I tried turning it off and on.",
    "priority": 3,
}


@pytest.fixture
def client(monkeypatch):
    """TestClient runs background tasks synchronously after the response."""
    calls: list[tuple] = []

    def fake_decide(short, desc, priority):
        calls.append((short, desc, priority))
        return Decision(decision=DecisionType.respond, message="Restart the printer.")

    monkeypatch.setattr(main, "decide", fake_decide)
    with TestClient(main.app) as c:
        c.decide_calls = calls  # type: ignore[attr-defined]
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_valid_payload_returns_202_and_runs_background(client):
    r = client.post("/webhook", json=GOOD)
    assert r.status_code == 202
    assert r.json() == {"status": "accepted", "incident": "INC0010001"}
    assert client.decide_calls == [(GOOD["short_description"], GOOD["description"], 3)]


def test_missing_field_returns_clean_422(client):
    bad = {k: v for k, v in GOOD.items() if k != "short_description"}
    r = client.post("/webhook", json=bad)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid webhook payload"
    assert client.decide_calls == []


def test_malformed_json_returns_422_not_500(client):
    r = client.post("/webhook", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert client.decide_calls == []


def test_empty_description_is_accepted(client):
    r = client.post("/webhook", json={**GOOD, "description": ""})
    assert r.status_code == 202


class TestSharedSecret:
    @pytest.fixture(autouse=True)
    def _secret(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "s3cr3t")
        from app.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_missing_secret_rejected(self, client):
        assert client.post("/webhook", json=GOOD).status_code == 401
        assert client.decide_calls == []

    def test_wrong_secret_rejected(self, client):
        r = client.post("/webhook", json=GOOD, headers={"X-Webhook-Secret": "nope"})
        assert r.status_code == 401

    def test_correct_secret_accepted(self, client):
        r = client.post("/webhook", json=GOOD, headers={"X-Webhook-Secret": "s3cr3t"})
        assert r.status_code == 202
