#!/usr/bin/env python3
"""Run the three golden tickets through the REAL Gemini model N times each and check the
decision every run. This is how FR6 is de-risked: temperature=0 is not fully deterministic,
so one lucky pass proves nothing.

Uses the service's own prompt + decision code, so it exercises exactly what runs in prod.
Respects the free tier: spacing between calls, and a retry on 429/503.

    uv run python scripts/eval_prompt.py                       # gemini-2.5-flash, N=3
    uv run python scripts/eval_prompt.py --n 5 --model gemini-2.5-flash-lite --spacing 4

Needs GEMINI_API_KEY in the environment (or .env).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from google.genai import errors as gerr  # noqa: E402

from app.decision import _call_gemini, _parse  # noqa: E402

GOLDENS = json.loads((ROOT / "tests/data/test_incidents.json").read_text())["incidents"]


def run_one(short: str, desc: str, retry_wait: float) -> str:
    for _ in range(4):
        try:
            return _parse(_call_gemini(short, desc, 3)).decision.value
        except (gerr.ClientError, gerr.ServerError) as exc:
            if getattr(exc, "code", None) in (429, 503):
                print(f"    {exc.code}; waiting {retry_wait:.0f}s", flush=True)
                time.sleep(retry_wait)
                continue
            raise
    return "ERROR"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default=None, help="overrides GEMINI_MODEL")
    ap.add_argument("--spacing", type=float, default=7.0, help="seconds between calls")
    ap.add_argument("--retry-wait", type=float, default=30.0)
    args = ap.parse_args()

    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"model={model}  n={args.n}  spacing={args.spacing}s\n")

    ok = True
    for tc in GOLDENS:
        expected = tc["expected_decision"]
        got: collections.Counter[str] = collections.Counter()
        for _ in range(args.n):
            got[run_one(tc["short_description"], tc["description"], args.retry_wait)] += 1
            time.sleep(args.spacing)
        hits = got[expected]
        verdict = "PASS " if hits == args.n else ("FLAKY" if hits else "FAIL ")
        ok &= hits == args.n
        print(f"[{verdict}] {expected:8} got={dict(got)}  <- {tc['short_description']}")

    print("\nALL GOLDENS STABLE" if ok else "\nNOT STABLE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
