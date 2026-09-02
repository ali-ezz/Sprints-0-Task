import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_from_env():
    s = Settings()
    assert s.servicenow_base == "https://dev-test.service-now.com"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.port == 8000


def test_trailing_slash_is_stripped(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://dev434590.service-now.com/")
    assert Settings().servicenow_base == "https://dev434590.service-now.com"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("on", True), ("ON", True), ("", True), ("off", False), ("false", False), ("0", False)],
)
def test_writeback_flag(monkeypatch, value, expected):
    monkeypatch.setenv("SERVICENOW_WRITEBACK", value)
    assert Settings().writeback_enabled is expected


def test_missing_required_var_fails_fast(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("app.config.Settings.model_config", {"env_file": None, "extra": "ignore"})
    with pytest.raises(ValidationError):
        Settings()
