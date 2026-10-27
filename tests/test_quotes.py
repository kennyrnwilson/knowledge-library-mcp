"""Tests for add_quote."""

import pytest

from knowledge_library_mcp.quotes import add_quote, format_quote, insert_quote, link_from_readme

def test_format_quote_has_four_parts():
    block = format_quote(
        "Exercise is the most potent longevity drug we have.",
        "Peter Attia", "Outlive", "ch. 11, p. 213", "It ranks exercise above any drug.",
        themes=["Exercise"], links=["[Zone 2](../../03-permanent-notes/z.md)"],
    )
    assert block == (
        '> "Exercise is the most potent longevity drug we have."\n'
        "> — Peter Attia, *Outlive*, ch. 11, p. 213\n"
        "\n"
        "- **Why:** It ranks exercise above any drug.\n"
        "- **Links:** [Zone 2](../../03-permanent-notes/z.md) · #quote/exercise"
    )


def test_format_quote_strips_existing_quote_marks_and_omits_empty_links():
    block = format_quote('"Hello."', "A", "T", "", "Because.")
    assert block.splitlines()[:2] == ['> "Hello."', "> — A, *T*"]
    assert "**Links:**" not in block


def test_format_quote_requires_why():
    with pytest.raises(ValueError):
        format_quote("text", "A", "T", "", "  ")


def test_insert_quote_appends_after_existing_quotes():
    note = "# T\n\n## 💬 Quotes & Highlights\n\n> \"old\"\n\n---\n\n*Last Updated: 2026-01-01*\n"
    out = insert_quote(note, "> \"new\"", "2026-10-22")
    assert out.index('"old"') < out.index('"new"') < out.index("---")
    assert "*Last Updated: 2026-10-22*" in out


def test_insert_quote_adds_a_missing_section_before_the_footer():
    note = "# T\n\n## Overview\n\nText.\n\n---\n\n*Last updated: 2026-01-01*\n"
    out = insert_quote(note, "> \"new\"", "2026-10-22")
    assert out.index("## Overview") < out.index("Quotes & Highlights") < out.index('"new"')
    assert out.index('"new"') < out.index("---")


def test_add_quote_creates_a_note_with_no_placeholders(temp_library):
    res = add_quote(temp_library, source_title="Four Thousand Weeks", author="Oliver Burkeman",
                    text="Time is finite.", why="The premise of the book.",
                    location="ch. 1", themes=["time"], today="2026-10-22")
    assert res == {"path": "02-literature-notes/books/four-thousand-weeks.md", "created": True,
                   "linked_from": None}
    note = (temp_library / res["path"]).read_text()
    assert note.startswith("# Four Thousand Weeks\n")
    assert "**Author/Creator:** Oliver Burkeman" in note
    assert "**Source Type:** Book\n" in note
    assert "*Created: 2026-10-22*" in note
    assert "YYYY" not in note and "Takeaway" not in note
    assert "> — Oliver Burkeman, *Four Thousand Weeks*, ch. 1" in note
    assert "#quote/time" in note


def test_add_quote_links_a_new_note_from_the_readme(temp_library):
    folder = temp_library / "02-literature-notes/books"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text(
        "# Books\n\nIntro.\n\n---\n\n**Tags:** #books\n\n*Last Updated: 2026-01-01*\n")
    res = add_quote(temp_library, source_title="Provincial Letters", author="Blaise Pascal",
                    text="Shorter.", why="Mine.", today="2026-10-27")
    assert res["linked_from"] == "02-literature-notes/books/README.md"
    readme = (folder / "README.md").read_text()
    assert "## Notes\n\n- [Provincial Letters](./provincial-letters.md) (Blaise Pascal)\n" in readme
    assert readme.index("## Notes") < readme.index("---")
    assert "*Last Updated: 2026-10-27*" in readme
    again = add_quote(temp_library, source_title="Provincial Letters", author="Blaise Pascal",
                      text="Again.", why="Mine.", today="2026-10-27")
    assert again["linked_from"] is None
    assert (folder / "README.md").read_text().count("provincial-letters.md") == 1


def test_link_from_readme_appends_to_an_existing_list():
    readme = "# B\n\n## Notes\n\n- [A](./a.md) (X)\n\n---\n"
    out = link_from_readme(readme, "B", "b.md", "Y", "2026-10-27")
    assert "- [A](./a.md) (X)\n- [B](./b.md) (Y)\n" in out


def test_format_quote_refuses_a_placeholder_why():
    with pytest.raises(ValueError, match="placeholder"):
        format_quote("text", "A", "T", "", "<your own sentence>")


def test_format_quote_names_the_speaker_first():
    block = format_quote("Make a love letter.", "Nancy Duarte", "Resonate", "ch. 3",
                         "A reminder.", said_by="Ken Haemer")
    assert block.splitlines()[1] == "> — Ken Haemer, quoted in Nancy Duarte, *Resonate*, ch. 3"


def test_add_quote_appends_to_existing_note(temp_library):
    first = add_quote(temp_library, source_title="Sample Book", author="Jane Doe",
                      text="One.", why="First.", category="books", today="2026-10-22")
    second = add_quote(temp_library, source_title="Sample Book", author="Jane Doe",
                       text="Two.", why="Second.", category="books", today="2026-10-22")
    assert first["created"] is True and second["created"] is False
    note = (temp_library / first["path"]).read_text()
    assert note.count("Quotes & Highlights") == 1
    assert note.index('"One."') < note.index('"Two."')


def test_add_quote_refuses_path_escape(temp_library):
    with pytest.raises(ValueError):
        add_quote(temp_library, source_title="X", author="A", text="t", why="w",
                  category="../../etc")
