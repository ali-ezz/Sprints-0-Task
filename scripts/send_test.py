#!/usr/bin/env python3
"""POST the three golden incident payloads to a running webhook service.

This is the offline loop for iterating on the prompt: run the service with
SERVICENOW_WRITEBACK=off, run this, and read the decisions from the service logs -- no
ServiceNow instance or tunnel needed.

    uv run python scripts/send_test.py
    uv run python scripts/send_test.py --url http://localhost:8000/webhook --secret S --force

--force also clears any existing local dedup rows for these synthetic incidents so they
can be replayed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent.parent
GOLDENS = json.loads((ROOT / "tests/data/test_incidents.json").read_text())["incidents"]


def _payload(index: int, tc: dict) -> dict:
    return {
        "incident_sys_id": f"GOLDEN-{index}",
        "number": f"GOLDEN{index:04d}",
        "short_description": tc["short_description"],
        "description": tc["description"],
        "priority": 3,
    }


def _clear_dedup(sys_ids: list[str]) -> None:
    db = ROOT / "dedup.sqlite3"
    if not db.exists():
        return
    con = sqlite3.connect(db)
    con.executemany(
        "DELETE FROM processed_incidents WHERE incident_sys_id = ?", [(s,) for s in sys_ids]
    )
    con.commit()
    print(f"cleared {con.total_changes} dedup row(s)")
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/webhook")
    ap.add_argument("--secret", default="")
    ap.add_argument("--force", action="store_true", help="clear local dedup rows first")
    args = ap.parse_args()

    payloads = [_payload(i, tc) for i, tc in enumerate(GOLDENS)]
    if args.force:
        _clear_dedup([p["incident_sys_id"] for p in payloads])

    for tc, payload in zip(GOLDENS, payloads, strict=True):
        headers = {"Content-Type": "application/json"}
        if args.secret:
            headers["X-Webhook-Secret"] = args.secret
        req = urllib.request.Request(
            args.url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(
                    f"[{resp.status}] {payload['number']}  expect={tc['expected_decision']:8}"
                    f"  <- {tc['short_description']}"
                )
                print(f"        {resp.read().decode()}")
        except urllib.error.HTTPError as exc:
            print(f"[{exc.code}] {payload['number']}: {exc.read().decode()}")
        except urllib.error.URLError as exc:
            print(f"could not reach {args.url}: {exc}")
            return 1

    print("\nRead the service logs for the decisions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
