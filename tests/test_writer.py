"""Tests for writer tools."""

from datetime import datetime, timezone

import pytest

from knowledge_library_mcp.writer import (
    NoteAlreadyExists,
    NoteNotFoundForUpdate,
    append_fleeting,
    create_note,
    slugify,
    update_note,
)


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_collapses_separators():
    assert slugify("  Multi   spaces--and--dashes  ") == "multi-spaces-and-dashes"


def test_slugify_strips_non_ascii_punct():
    assert slugify("Don't, can't & won't") == "dont-cant-wont"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        slugify("   !!!   ")


def test_create_fleeting_note(temp_library):
    path = create_note(temp_library, kind="fleeting", area_or_path="", title="A New Idea", content="body")
    assert path == "01-fleeting-notes/a-new-idea.md"
    assert (temp_library / path).read_text() == "body"


def test_create_fleeting_note_with_subpath(temp_library):
    path = create_note(temp_library, kind="fleeting", area_or_path="credit-products",
                       title="CDS basics", content="x")
    assert path == "01-fleeting-notes/credit-products/cds-basics.md"
    assert (temp_library / path).is_file()


def test_create_permanent_requires_nonempty_area_or_path(temp_library):
    with pytest.raises(ValueError):
        create_note(temp_library, kind="permanent", area_or_path="", title="X", content="y")


def test_create_permanent_with_area(temp_library):
    path = create_note(temp_library, kind="permanent", area_or_path="professional",
                       title="Bias to action", content="ship.")
    assert path == "03-permanent-notes/professional/bias-to-action.md"


def test_create_guidance(temp_library):
    path = create_note(temp_library, kind="guidance", area_or_path="wellbeing",
                       title="Sleep schedule", content="lights out 22:30.")
    assert path == "04-guidance/wellbeing/sleep-schedule.md"


def test_create_guidance_with_non_canonical_subpath(temp_library):
    path = create_note(temp_library, kind="guidance", area_or_path="as-a-healthy-man",
                       title="Calm your mind", content="breathe.")
    assert path == "04-guidance/as-a-healthy-man/calm-your-mind.md"
    assert (temp_library / path).is_file()


def test_create_permanent_with_non_canonical_subpath(temp_library):
    path = create_note(temp_library, kind="permanent", area_or_path="mental-health",
                       title="Cognitive distortions", content="all-or-nothing thinking.")
    assert path == "03-permanent-notes/mental-health/cognitive-distortions.md"
    assert (temp_library / path).is_file()


def test_create_literature(temp_library):
    path = create_note(temp_library, kind="literature", area_or_path="", title="Atomic Habits",
                       content="habit stacking.")
    assert path == "02-literature-notes/atomic-habits.md"


def test_create_project_creates_subdir_with_readme(temp_library):
    path = create_note(temp_library, kind="project", area_or_path="", title="Garden Reno",
                       content="objective: rebuild fence.")
    assert path == "05-projects/garden-reno/README.md"
    assert (temp_library / path).is_file()


def test_create_refuses_overwrite(temp_library):
    create_note(temp_library, kind="fleeting", area_or_path="", title="First", content="a")
    with pytest.raises(NoteAlreadyExists):
        create_note(temp_library, kind="fleeting", area_or_path="", title="First", content="b")


def test_update_note_overwrites(temp_library):
    rel = "01-fleeting-notes/topic-thought.md"
    update_note(temp_library, rel, "new content")
    assert (temp_library / rel).read_text() == "new content"


def test_update_note_refuses_to_create_new(temp_library):
    with pytest.raises(NoteNotFoundForUpdate):
        update_note(temp_library, "01-fleeting-notes/does-not-exist.md", "x")


def test_append_fleeting_creates_dated_file_if_missing(temp_library, monkeypatch):
    # Pin "today" to a date NOT already in the fixture library.
    fake_today = datetime(2030, 1, 2, 9, 30, 0, tzinfo=timezone.utc)

    class _F(datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_today

    monkeypatch.setattr("knowledge_library_mcp.writer.datetime", _F)

    path = append_fleeting(temp_library, "first capture")
    assert path == "01-fleeting-notes/2030-01-02.md"
    text = (temp_library / path).read_text()
    assert "first capture" in text
    assert "## 09:30:00" in text


def test_append_fleeting_appends_to_existing(temp_library, monkeypatch):
    # Use the date already present in the fixture library
    fake = datetime(2026, 5, 9, 16, 45, 0, tzinfo=timezone.utc)

    class _F(datetime):
        @classmethod
        def now(cls, tz=None):
            return fake

    monkeypatch.setattr("knowledge_library_mcp.writer.datetime", _F)

    path = append_fleeting(temp_library, "later thought")
    text = (temp_library / path).read_text()
    # original content preserved
    assert "Quick capture" in text
    # new entry appended with timestamp
    assert "## 16:45:00" in text
    assert "later thought" in text
