#!/usr/bin/env python3
"""POST incident payloads to a running webhook service.

Default: the three golden tickets with synthetic ids -- the offline loop for iterating on
the prompt (run the service with SERVICENOW_WRITEBACK=off and read the decisions from the
logs; no ServiceNow instance or tunnel needed).

    uv run python scripts/send_test.py
    uv run python scripts/send_test.py --url http://localhost:8000/webhook --secret S --force

Single real incident (e.g. to drive the write-back onto a ticket you created in the PDI,
for before/after screenshots): pass --sys-id (and friends).

    uv run python scripts/send_test.py --sys-id 1c74... --number INC0010007 \
        --short "Printer not printing" --description "tried off and on" [--force]

--force clears the matching local dedup row(s) first so the same incident can be replayed.
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


def _golden_payloads() -> list[dict]:
    return [
        {
            "incident_sys_id": f"GOLDEN-{i}",
            "number": f"GOLDEN{i:04d}",
            "short_description": tc["short_description"],
            "description": tc["description"],
            "priority": 3,
            "_expect": tc["expected_decision"],
        }
        for i, tc in enumerate(GOLDENS)
    ]


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


def _post(url: str, payload: dict, secret: str) -> int:
    expect = payload.pop("_expect", None)
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    label = f"{payload['number']}" + (f"  expect={expect}" if expect else "")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[{resp.status}] {label}\n        {resp.read().decode()}")
        return 0
    except urllib.error.HTTPError as exc:
        print(f"[{exc.code}] {label}: {exc.read().decode()}")
        return 0
    except urllib.error.URLError as exc:
        print(f"could not reach {url}: {exc}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/webhook")
    ap.add_argument("--secret", default="")
    ap.add_argument("--force", action="store_true", help="clear matching local dedup rows first")
    ap.add_argument("--sys-id", help="send ONE real incident instead of the goldens")
    ap.add_argument("--number", default="INC0000000")
    ap.add_argument("--short", default="Test incident")
    ap.add_argument("--description", default="")
    ap.add_argument("--priority", type=int, default=3)
    args = ap.parse_args()

    if args.sys_id:
        payloads = [
            {
                "incident_sys_id": args.sys_id,
                "number": args.number,
                "short_description": args.short,
                "description": args.description,
                "priority": args.priority,
            }
        ]
    else:
        payloads = _golden_payloads()

    if args.force:
        _clear_dedup([p["incident_sys_id"] for p in payloads])

    rc = 0
    for payload in payloads:
        rc |= _post(args.url, payload, args.secret)
    print("\nRead the service logs for the decisions.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
