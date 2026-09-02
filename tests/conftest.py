"""Test-wide fixtures. Sets dummy env vars so `Settings()` never needs real secrets.

Environment variables take precedence over the .env file in pydantic-settings, so these
override any real local .env during tests.
"""

import os

os.environ.setdefault("SERVICENOW_INSTANCE_URL", "https://dev-test.service-now.com")
os.environ.setdefault("SERVICENOW_USERNAME", "admin")
os.environ.setdefault("SERVICENOW_PASSWORD", "test-password")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("WEBHOOK_SHARED_SECRET", "")
os.environ.setdefault("SERVICENOW_WRITEBACK", "off")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Each test gets a fresh Settings() in case it tweaks env vars."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
