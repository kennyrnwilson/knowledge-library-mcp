"""Tests for ripgrep search."""

from knowledge_library_mcp.search import SearchHit, search_notes


def test_search_finds_phrase_across_areas(fixture_library):
    hits = search_notes(fixture_library, "deep work")
    paths = {h.path for h in hits}
    assert "03-permanent-notes/professional/deep-work-principle.md" in paths
    # also matches in archive (which we don't filter by default)
    assert any("07-archive" in p for p in paths)


def test_search_returns_searchhit_records(fixture_library):
    hit = search_notes(fixture_library, "deep work")[0]
    assert isinstance(hit, SearchHit)
    assert hit.line_number > 0
    assert hit.line.strip()


def test_search_empty_query_returns_empty(fixture_library):
    assert search_notes(fixture_library, "  ") == []


def test_search_unknown_phrase_returns_empty(fixture_library):
    assert search_notes(fixture_library, "xyzzy-no-such-phrase") == []


def test_search_area_scope_restricts_results(fixture_library):
    hits = search_notes(fixture_library, "deep work", area="professional")
    paths = {h.path for h in hits}
    # all hits must lie under either 03-permanent-notes/professional or 04-guidance/professional
    assert all(
        p.startswith("03-permanent-notes/professional/") or p.startswith("04-guidance/professional/")
        for p in paths
    )


def test_search_area_unknown_raises(fixture_library):
    import pytest
    with pytest.raises(ValueError):
        search_notes(fixture_library, "anything", area="not-an-area")
