"""Guards prompt.txt: it must stay in sync with the KB and define the three decisions."""

from app.knowledge import load_kb_articles
from app.prompt import system_instruction, user_turn


def test_every_kb_article_text_is_in_the_prompt():
    prompt = system_instruction()
    for article in load_kb_articles():
        assert article["text"] in prompt, f"KB article {article['id']} missing from prompt.txt"


def test_prompt_defines_the_three_decisions():
    prompt = system_instruction()
    for word in ("respond", "ask", "escalate"):
        assert f'"{word}"' in prompt


def test_prompt_forbids_outside_knowledge():
    prompt = system_instruction().lower()
    assert "only" in prompt and "knowledge base" in prompt


def test_user_turn_fences_the_ticket_and_handles_empty_description():
    turn = user_turn("Cannot send email", "   ", 3)
    assert turn.startswith("<ticket>") and turn.endswith("</ticket>")
    assert "Short description: Cannot send email" in turn
    assert "(none provided)" in turn
    assert "Priority: 3" in turn


def test_user_turn_handles_missing_priority():
    assert "Priority: (unset)" in user_turn("x", "y", None)
