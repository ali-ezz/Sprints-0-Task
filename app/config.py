"""Runtime configuration, loaded from environment / .env (never hard-coded).

Import `get_settings()` lazily (inside functions or the app lifespan) so that merely
importing a module does not require credentials to be present — this keeps unit tests
free of real secrets.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_FALSEY = {"off", "false", "0", "no", "n"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ServiceNow PDI
    servicenow_instance_url: str = Field(..., description="https://devXXXXXX.service-now.com")
    servicenow_username: str
    servicenow_password: str
    servicenow_close_code: str = "Solution provided"

    # Gemini
    gemini_api_key: str
    # "gemini-flash-latest" is an alias tracking the current Flash model. A pinned id like
    # "gemini-2.5-flash" also works; each id has its own free-tier daily quota bucket.
    gemini_model: str = "gemini-flash-latest"

    # Service
    port: int = 8000
    webhook_shared_secret: str = ""
    servicenow_writeback: str = "on"
    dedup_db_path: str = "dedup.sqlite3"

    @property
    def servicenow_base(self) -> str:
        return self.servicenow_instance_url.rstrip("/")

    @property
    def writeback_enabled(self) -> bool:
        return self.servicenow_writeback.strip().lower() not in _FALSEY


@lru_cache
def get_settings() -> Settings:
    """Cached accessor. Raises pydantic ValidationError (fail-fast) if required vars are missing."""
    return Settings()  # type: ignore[call-arg]
