"""Tests for areas module."""

from knowledge_library_mcp.areas import AREAS, area_for_path


def test_areas_has_six_canonical_entries():
    assert len(AREAS) == 6
    assert set(AREAS) == {
        "professional", "wellbeing", "productivity",
        "parenting", "leisure", "personal-development",
    }


def test_area_for_path_under_permanent_notes():
    assert area_for_path("03-permanent-notes/professional/x.md") == "professional"


def test_area_for_path_under_guidance():
    assert area_for_path("04-guidance/wellbeing/y.md") == "wellbeing"


def test_area_for_path_outside_areas_returns_none():
    assert area_for_path("01-fleeting-notes/2026-05-09.md") is None
    assert area_for_path("05-projects/foo/README.md") is None


def test_area_for_path_unknown_area_returns_none():
    assert area_for_path("03-permanent-notes/not-an-area/x.md") is None
