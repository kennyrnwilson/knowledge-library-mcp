"""Tests for notes filesystem readers."""

import pytest

from knowledge_library_mcp.notes import (
    NoteNotFound,
    get_guidance,
    get_note,
    list_permanent_notes,
    list_projects,
)


def test_list_permanent_notes_filters_by_area(fixture_library):
    notes = list_permanent_notes(fixture_library, area="professional")
    paths = {n["path"] for n in notes}
    assert "03-permanent-notes/professional/deep-work-principle.md" in paths
    # wellbeing's note must NOT be in the professional list
    assert all("wellbeing/" not in p for p in paths)


def test_list_permanent_notes_unknown_area_raises(fixture_library):
    with pytest.raises(ValueError) as exc:
        list_permanent_notes(fixture_library, area="not-an-area")
    assert "area" in str(exc.value).lower()


def test_get_note_returns_text(fixture_library):
    text = get_note(fixture_library, "01-fleeting-notes/topic-thought.md")
    assert "deep work" in text.lower()


def test_get_note_missing_raises_note_not_found(fixture_library):
    with pytest.raises(NoteNotFound):
        get_note(fixture_library, "01-fleeting-notes/does-not-exist.md")


def test_get_note_path_traversal_blocked(fixture_library):
    with pytest.raises(ValueError):
        get_note(fixture_library, "../etc/passwd")


def test_list_projects_returns_dirs_with_readme(fixture_library):
    projects = list_projects(fixture_library)
    slugs = {p["slug"] for p in projects}
    assert "sample-project" in slugs


def test_get_guidance_by_topic_slug(fixture_library):
    text = get_guidance(fixture_library, "code-review-checklist")
    assert "code review checklist" in text.lower()


def test_get_guidance_unknown_topic_raises(fixture_library):
    with pytest.raises(NoteNotFound):
        get_guidance(fixture_library, "no-such-guidance-topic")


def test_get_guidance_path_traversal_blocked(fixture_library):
    with pytest.raises(ValueError):
        get_guidance(fixture_library, "../../etc/passwd")


def test_get_guidance_empty_topic_raises(fixture_library):
    with pytest.raises(ValueError):
        get_guidance(fixture_library, "")


def test_get_guidance_finds_non_canonical_subdir(fixture_library):
    text = get_guidance(fixture_library, "manage-stress")
    assert "manage stress" in text.lower()
