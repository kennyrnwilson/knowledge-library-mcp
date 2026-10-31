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
    assert res["state"] == dict.fromkeys(("MISSION.md", "RESOURCES.md", "NOTES.md", "PLAN.md"))
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


# ---- save_lesson_plan --------------------------------------------------------

from knowledge_library_mcp.teach import save_lesson_plan, upsert_plan_section  # noqa: E402


@pytest.fixture
def template(temp_library: Path) -> Path:
    assets = temp_library / "05-projects" / "use-the-system" / "teach" / "assets"
    assets.mkdir(parents=True)
    (assets / "course.css").write_text("body {}")
    (assets / "recall.js").write_text("// recall")
    index = temp_library / "05-projects" / "README.md"
    index.write_text(
        "# Projects\n\n## Active Projects\n\n| Project | Status |\n|---|---|\n"
        "| [Explore](./explore/README.md) | Ongoing |\n\n## Completed Projects\n"
    )
    return assets


def _save(lib: Path, **kw):
    args = dict(book_slug="make-it-stick", title="Make It Stick", author="Brown",
                section="Chapter 2: To learn, retrieve", plan="1. **Retrieve** — do it.",
                why="Study for the exam.", today="2026-10-31")
    return save_lesson_plan(lib, **{**args, **kw})


def test_first_plan_creates_the_book_workspace(temp_library: Path, template: Path):
    r = _save(temp_library)
    ws = temp_library / "05-projects" / "make-it-stick" / "teach"
    assert r["created"] is True
    assert r["plan_url"] == "/knowledge/projects/make-it-stick/teach/plan/"
    assert "book-library/make-it-stick/README.md" in (ws.parent / "README.md").read_text()
    assert "Study for the exam." in (ws / "MISSION.md").read_text()
    assert (ws / "assets" / "recall.js").read_text() == "// recall"
    plan = (ws / "PLAN.md").read_text()
    assert "## Chapter 2: To learn, retrieve\n\n1. **Retrieve** — do it." in plan
    index = (temp_library / "05-projects" / "README.md").read_text()
    assert "| [Make It Stick](./make-it-stick/README.md) | In progress |" in index
    assert index.index("make-it-stick") < index.index("## Completed Projects")
    assert "05-projects/README.md" in r["paths"]
    assert "05-projects/make-it-stick/teach/assets/recall.js" in r["paths"]


def test_saving_a_section_again_replaces_it_and_keeps_the_rest(temp_library, template):
    _save(temp_library)
    _save(temp_library, section="Chapter 3: Mix up", plan="1. Interleave.", why="")
    r = _save(temp_library, plan="1. Retrieve, revised.", why="")
    plan = (temp_library / r["plan"]).read_text()
    assert r["created"] is False
    assert r["paths"] == ["05-projects/make-it-stick/teach/PLAN.md"]
    assert "Retrieve, revised." in plan and "— do it." not in plan
    assert plan.index("Chapter 2") < plan.index("Chapter 3")
    assert plan.count("## Chapter 2") == 1


def test_new_book_course_needs_why(temp_library, template):
    with pytest.raises(TeachError, match="why"):
        _save(temp_library, why="")


def test_refuses_a_project_about_something_else(temp_library, template):
    other = temp_library / "05-projects" / "make-it-stick"
    other.mkdir(parents=True)
    (other / "README.md").write_text("# Make it stick: a glue project\n")
    with pytest.raises(TeachError, match="not about this book"):
        _save(temp_library)


def test_plan_is_part_of_the_workspace_state(temp_library, template):
    _save(temp_library)
    state = teach_start(temp_library, "make-it-stick")["state"]
    assert "Chapter 2" in state["PLAN.md"]
    write_teach_file(temp_library, "make-it-stick", "PLAN.md", "# edited\n")


def test_upsert_section_appends_when_missing():
    out = upsert_plan_section("# Plan\n", "Whole book", "1. A.")
    assert out == "# Plan\n\n## Whole book\n\n1. A.\n"
