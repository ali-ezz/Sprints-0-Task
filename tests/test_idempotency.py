import concurrent.futures

import pytest

from app.idempotency import Idempotency


@pytest.fixture
def idem(tmp_path):
    return Idempotency(str(tmp_path / "dedup.sqlite3"))


def test_first_claim_wins_second_loses(idem):
    assert idem.claim("sys1", "INC001") is True
    assert idem.claim("sys1", "INC001") is False
    assert idem.status("sys1") == "processing"


def test_completed_incident_is_not_reprocessed(idem):
    idem.claim("sys1", "INC001")
    idem.complete("sys1", "respond")
    assert idem.status("sys1") == "done"
    assert idem.claim("sys1", "INC001") is False


def test_failed_incident_can_be_reclaimed(idem):
    idem.claim("sys1", "INC001")
    idem.fail("sys1")
    assert idem.status("sys1") == "failed"
    assert idem.claim("sys1", "INC001") is True
    assert idem.status("sys1") == "processing"


def test_unknown_incident_has_no_status(idem):
    assert idem.status("nope") is None


def test_concurrent_claims_exactly_one_winner(tmp_path):
    db = str(tmp_path / "race.sqlite3")
    Idempotency(db)  # create schema once

    def worker() -> bool:
        return Idempotency(db).claim("same", "INC999")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: worker(), range(16)))

    assert results.count(True) == 1
    assert results.count(False) == 15
