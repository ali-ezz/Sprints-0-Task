"""The webhook request model — mirrors payload_contract.json.

`description` may be empty or absent (per the contract); `priority` may be null when the
incident has no priority set. `short_description` is always present.
"""

from pydantic import BaseModel, Field, field_validator


class IncidentPayload(BaseModel):
    incident_sys_id: str = Field(min_length=1)
    number: str = Field(min_length=1)
    short_description: str = Field(min_length=1)
    description: str = ""
    priority: int | None = None

    @field_validator("description", mode="before")
    @classmethod
    def _null_description_to_empty(cls, v: object) -> object:
        return "" if v is None else v
