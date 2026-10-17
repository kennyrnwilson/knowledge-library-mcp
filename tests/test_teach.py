"""Tests for the teaching-workspace functions (the `teach` skill over MCP)."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_library_mcp.teach import (
    TeachError,
    edit_teach_file,
    get_lesson,
    list_lessons,
    load_instructions,
    published_url,
    teach_start,
    write_teach_file,
)

LESSON = """<!doctype html><html><head><title>0001 — Active voice</title>
<style>p { color: red }</style><link rel="stylesheet" href="../assets/course.css"></head>
<body><h1>Write in the active voice</h1><p>Close the valve.</p>
<script>console.log("hidden")</script></body></html>"""


@pytest.fixture
def workspace(temp_library: Path) -> Path:
    ws = temp_library / "05-projects" / "sample-project" / "teach"
    (ws / "lessons").mkdir(parents=True)
    (ws / "lessons" / "0001-active-voice.html").write_text(LESSON)
    (ws / "learning-records").mkdir()
    (ws / "learning-records" / "0001-voice.md").write_text("# Voice\n")
    (ws / "assets").mkdir()
    (ws / "assets" / "course.css").write_text("body { margin: 0 }")
    (ws / "MISSION.md").write_text("# Mission\n")
    return ws


def test_instructions_put_preamble_before_skill():
    text = load_instructions()
    assert text.index("Teaching through the knowledge-library MCP server") < text.index(
        "## Teaching Workspace"
    )
    assert "LEARNING-RECORD-FORMAT.md" in text


def test_published_url_strips_prefix_from_directories_only():
    assert (
        published_url("05-projects/p/teach/lessons/0001-x.html")
        == "/knowledge/projects/p/teach/lessons/0001-x.html"
    )


@pytest.mark.parametrize("path, url", [
    ("05-projects/p/teach/MISSION.md", "/knowledge/projects/p/teach/mission/"),
    ("05-projects/p/teach/learning-records/0001-voice.md",
     "/knowledge/projects/p/teach/learning-records/voice/"),
    ("05-projects/p/README.md", "/knowledge/projects/p/"),
])
def test_published_url_for_markdown_matches_portal_pages(path, url):
    assert published_url(path) == url


def test_teach_start_on_new_workspace(temp_library):
    res = teach_start(temp_library, "sample-project")
    assert res["exists"] is False
    assert res["workspace"] == "05-projects/sample-project/teach"
    assert res["state"] == {"MISSION.md": None, "RESOURCES.md": None, "NOTES.md": None}
    assert res["lessons"] == [] and res["assets"] == []
    assert "## Teaching Workspace" in res["instructions"]


def test_teach_start_returns_state_and_lists_lessons_without_html(temp_library, workspace):
    res = teach_start(temp_library, "sample-project")
    assert res["state"]["MISSION.md"] == "# Mission\n"
    assert res["learning_records"] == [
        {"path": "learning-records/0001-voice.md", "content": "# Voice\n"}
    ]
    assert res["assets"] == [{"path": "assets/course.css", "content": "body { margin: 0 }"}]
    assert res["lessons"][0]["title"] == "0001 — Active voice"
    assert "Close the valve" not in str(res["lessons"])


def test_teach_start_rejects_unknown_or_bad_project(temp_library):
    with pytest.raises(TeachError, match="no such project"):
        teach_start(temp_library, "missing")
    with pytest.raises(TeachError, match="invalid project name"):
        teach_start(temp_library, "../01-fleeting-notes")


def test_list_lessons(temp_library, workspace):
    assert list_lessons(temp_library, "sample-project") == [{
        "number": 1,
        "title": "0001 — Active voice",
        "path": "05-projects/sample-project/teach/lessons/0001-active-voice.html",
        "url": "/knowledge/projects/sample-project/teach/lessons/0001-active-voice.html",
    }]


def test_get_lesson_returns_text_without_markup(temp_library, workspace):
    text = get_lesson(temp_library, "05-projects/sample-project/teach/lessons/0001-active-voice.html")
    assert text.startswith("# 0001 — Active voice")
    assert "Close the valve." in text
    assert "color: red" not in text and "hidden" not in text and "<" not in text


@pytest.mark.parametrize("path", [
    "03-permanent-notes/professional/deep-work-principle.md",
    "05-projects/sample-project/README.md",
    "05-projects/sample-project/teach/../../../03-permanent-notes/x.html",
])
def test_get_lesson_refuses_non_workspace_pages(temp_library, workspace, path):
    with pytest.raises(TeachError):
        get_lesson(temp_library, path)


def test_write_teach_file_creates_and_overwrites(temp_library):
    res = write_teach_file(temp_library, "sample-project", "lessons/0001-a.html", "<p>one</p>")
    assert res == {
        "path": "05-projects/sample-project/teach/lessons/0001-a.html",
        "url": "/knowledge/projects/sample-project/teach/lessons/0001-a.html",
    }
    write_teach_file(temp_library, "sample-project", "lessons/0001-a.html", "<p>two</p>")
    assert (temp_library / res["path"]).read_text() == "<p>two</p>"


@pytest.mark.parametrize("path, message", [
    ("lessons/data.json", "file type not allowed"),
    ("README.md", "top-level file"),
    ("scripts/x.js", "path must start with"),
    ("lessons/../../README.md", "without '..'"),
    ("/etc/passwd.md", "without '..'"),
])
def test_write_teach_file_refuses_bad_paths(temp_library, path, message):
    with pytest.raises(TeachError, match=message):
        write_teach_file(temp_library, "sample-project", path, "x")


def test_edit_teach_file_replaces_unique_text(temp_library, workspace):
    edit_teach_file(temp_library, "sample-project", "MISSION.md", "Mission", "Why I learn")
    assert (workspace / "MISSION.md").read_text() == "# Why I learn\n"


def test_edit_teach_file_requires_exactly_one_match(temp_library, workspace):
    with pytest.raises(TeachError, match="found 0"):
        edit_teach_file(temp_library, "sample-project", "MISSION.md", "absent", "x")
    (workspace / "NOTES.md").write_text("a a")
    with pytest.raises(TeachError, match="found 2"):
        edit_teach_file(temp_library, "sample-project", "NOTES.md", "a", "b")
    with pytest.raises(TeachError, match="does not exist"):
        edit_teach_file(temp_library, "sample-project", "RESOURCES.md", "a", "b")
