import pytest
from pydantic import ValidationError

from app.models import IncidentPayload

GOOD = {
    "incident_sys_id": "abc123",
    "number": "INC0010001",
    "short_description": "Printer not printing",
    "description": "It was working yesterday.",
    "priority": 3,
}


def test_full_payload():
    p = IncidentPayload(**GOOD)
    assert p.number == "INC0010001"
    assert p.priority == 3


def test_description_optional_and_null_becomes_empty():
    assert IncidentPayload(**{**GOOD, "description": None}).description == ""
    no_desc = {k: v for k, v in GOOD.items() if k != "description"}
    assert IncidentPayload(**no_desc).description == ""


def test_priority_optional():
    assert IncidentPayload(**{**GOOD, "priority": None}).priority is None


@pytest.mark.parametrize("field", ["incident_sys_id", "number", "short_description"])
def test_required_fields_reject_empty(field):
    with pytest.raises(ValidationError):
        IncidentPayload(**{**GOOD, field: ""})


def test_missing_required_field_rejected():
    bad = {k: v for k, v in GOOD.items() if k != "incident_sys_id"}
    with pytest.raises(ValidationError):
        IncidentPayload(**bad)
