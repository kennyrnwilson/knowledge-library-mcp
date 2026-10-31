"""Tests for the reading app's literature notes, anchors and read-back."""

import pytest

from knowledge_library_mcp.git_ops import list_pending_changes, save_changes
from knowledge_library_mcp.quotes import add_quote
from knowledge_library_mcp.reading import add_literature_section, source_annotations
from knowledge_library_mcp.writer import append_fleeting


def test_add_literature_section_creates_the_note_with_a_reading_section(temp_library):
    res = add_literature_section(temp_library, "deep-work", "Deep Work", "Cal Newport",
                                 "Depth is a skill.", location="ch. 1", passage="The passage.",
                                 anchor="epubcfi(/6/4!/4)", today="2026-10-31")
    assert res["path"] == "02-literature-notes/books/deep-work.md" and res["created"]
    note = (temp_library / res["path"]).read_text()
    assert note.startswith("# Deep Work\n")
    assert ("### ch. 1 · 2026-10-31\n\n> The passage.\n\nDepth is a skill.\n\n"
            "<!-- anchor: epubcfi(/6/4!/4) -->") in note
    assert note.index("Reading Notes") < note.index("Quotes & Highlights") < note.index("\n---\n")


def test_sections_append_in_order(temp_library):
    for text in ("One.", "Two."):
        add_literature_section(temp_library, "deep-work", "Deep Work", "C N", text,
                               today="2026-10-31")
    note = (temp_library / "02-literature-notes/books/deep-work.md").read_text()
    assert note.count("Reading Notes") == 1
    assert note.index("One.") < note.index("Two.")


def test_source_annotations_reads_back_all_three_kinds(temp_library):
    add_literature_section(temp_library, "deep-work", "Deep Work", "Cal Newport", "Mine.",
                           location="ch. 2", anchor="epubcfi(/6/8!)", today="2026-10-31")
    add_quote(temp_library, "Deep Work", "Cal Newport", "Clarity about what matters.",
              "It names the goal.", location="ch. 2", anchor="epubcfi(/6/9!)",
              today="2026-10-31")
    append_fleeting(temp_library, "From [Deep Work](book-library/deep-work/README.md): idea.",
                    anchor="epubcfi(/6/10!)")
    append_fleeting(temp_library, "Unrelated thought.")
    got = source_annotations(temp_library, "deep-work")
    assert got["literature_note"] == "02-literature-notes/books/deep-work.md"
    assert got["literature"] == [
        {"kind": "literature", "text": "Mine.", "passage": "", "location": "ch. 2",
         "date": "2026-10-31", "anchor": "epubcfi(/6/8!)"},
    ]
    assert got["quotes"] == [
        {"kind": "quote", "text": "Clarity about what matters.", "location": "ch. 2",
         "why": "It names the goal.", "anchor": "epubcfi(/6/9!)"},
    ]
    assert len(got["fleeting"]) == 1
    assert got["fleeting"][0]["anchor"] == "epubcfi(/6/10!)"
    assert "idea." in got["fleeting"][0]["text"]


def test_source_annotations_for_an_unknown_book_is_empty(temp_library):
    got = source_annotations(temp_library, "no-such-book")
    assert got == {"slug": "no-such-book", "literature_note": "", "quotes": [],
                   "literature": [], "fleeting": []}


def test_anchor_rejects_a_comment_terminator(temp_library):
    with pytest.raises(ValueError):
        append_fleeting(temp_library, "x", anchor="a -->")


def test_save_with_paths_leaves_other_drafts_on_disk(temp_git_library):
    lib = temp_git_library
    add_literature_section(lib, "deep-work", "Deep Work", "C N", "Mine.", today="2026-10-31")
    (lib / "07-archive/old-thought.md").write_text("someone else's draft\n")
    result = save_changes(lib, message="reading", paths=["02-literature-notes/books/deep-work.md"])
    assert result.committed and result.pushed
    assert [p["path"] for p in list_pending_changes(lib)] == ["07-archive/old-thought.md"]
