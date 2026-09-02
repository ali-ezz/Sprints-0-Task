"""Loads the five knowledge-base articles — the ONLY source the Gemini prompt may use.

`kb_articles.json` is vendored at `app/data/kb_articles.json` (copied verbatim from the
task asset pack) so a fresh clone works with no external files.
"""

import json
from functools import lru_cache
from pathlib import Path

_KB_PATH = Path(__file__).parent / "data" / "kb_articles.json"


@lru_cache
def load_kb_articles() -> list[dict]:
    data = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    articles = data.get("articles") or []
    if not articles:
        raise ValueError(f"{_KB_PATH} contains no articles")
    for a in articles:
        if "id" not in a or "text" not in a:
            raise ValueError(f"malformed KB article: {a!r}")
    return articles


def kb_as_prompt_block() -> str:
    """The KB rendered exactly as it is injected into the prompt (one line per article)."""
    return "\n".join(f"[{a['id']}] {a['text']}" for a in load_kb_articles())
