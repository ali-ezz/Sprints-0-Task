"""Builds the exact text sent to Gemini.

`prompt.txt` (repo root) is the system instruction, verbatim — it already contains the
five KB articles inline. It is committed as deliverable #4 ("your Gemini prompt ... exactly
as the service sends it"). `tests/test_prompt.py` guards it against drifting from
`kb_articles.json`. The per-ticket `<ticket>` block is the user turn.
"""

from functools import lru_cache
from pathlib import Path

_PROMPT_PATH = Path(__file__).parent.parent / "prompt.txt"


@lru_cache
def system_instruction() -> str:
    """The system instruction, exactly as sent."""
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def user_turn(short_description: str, description: str, priority: int | None) -> str:
    """The user message for one ticket, exactly as sent."""
    return (
        "<ticket>\n"
        f"Short description: {short_description}\n"
        f"Details: {description.strip() or '(none provided)'}\n"
        f"Priority: {priority if priority is not None else '(unset)'}\n"
        "</ticket>"
    )
