"""Test-wide fixtures.

Force dummy credentials into the environment so `Settings()` is deterministic, never needs
real secrets, and never accidentally picks up a real local `.env` or exported shell vars.
Environment variables take precedence over the `.env` file in pydantic-settings.
"""

import os

_TEST_ENV = {
    "SERVICENOW_INSTANCE_URL": "https://dev-test.service-now.com",
    "SERVICENOW_USERNAME": "admin",
    "SERVICENOW_PASSWORD": "test-password",
    "GEMINI_API_KEY": "test-gemini-key",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "WEBHOOK_SHARED_SECRET": "",
    "SERVICENOW_WRITEBACK": "off",
}
os.environ.update(_TEST_ENV)  # force, not setdefault


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
