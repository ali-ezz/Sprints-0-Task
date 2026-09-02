from app.knowledge import kb_as_prompt_block, load_kb_articles


def test_loads_five_articles():
    articles = load_kb_articles()
    assert len(articles) == 5
    assert [a["id"] for a in articles] == [1, 2, 3, 4, 5]


def test_prompt_block_shape():
    block = kb_as_prompt_block()
    lines = block.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("[1] ")
    # content from the real asset pack
    assert "Printer not printing" in block
    assert "port 587" in block
    assert "incognito" in block
