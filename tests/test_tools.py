"""End-to-end MCP tool tests (in-process FastMCP)."""

from __future__ import annotations

import json

import pytest

from knowledge_library_mcp.server import build_server


@pytest.fixture
def server(temp_library, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_LIBRARY_ROOT", str(temp_library))
    return build_server()


@pytest.fixture
def git_server(temp_git_library, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_LIBRARY_ROOT", str(temp_git_library))
    return build_server()


def _extract(call_tool_result):
    if isinstance(call_tool_result, tuple) and len(call_tool_result) == 2:
        content, structured = call_tool_result
        if structured is not None:
            if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
                return structured["result"]
            return structured
        return _from_content(content)
    if isinstance(call_tool_result, list):
        return _from_content(call_tool_result)
    return call_tool_result


def _from_content(content):
    for item in content or []:
        if getattr(item, "type", None) == "text":
            try:
                return json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                return item.text
    return None


@pytest.mark.asyncio
async def test_list_areas(server):
    res = _extract(await server.call_tool("list_areas", {}))
    assert "professional" in res and len(res) == 6


@pytest.mark.asyncio
async def test_search_notes(server):
    res = _extract(await server.call_tool("search_notes", {"query": "deep work"}))
    assert any(h["path"].endswith("deep-work-principle.md") for h in res)


@pytest.mark.asyncio
async def test_search_notes_area_scope(server):
    res = _extract(await server.call_tool(
        "search_notes", {"query": "deep work", "area": "professional"}
    ))
    assert all(h["path"].startswith(("03-permanent-notes/professional/", "04-guidance/professional/"))
               for h in res)


@pytest.mark.asyncio
async def test_list_permanent_notes(server):
    res = _extract(await server.call_tool(
        "list_permanent_notes", {"area": "professional"}
    ))
    assert any(n["path"].endswith("deep-work-principle.md") for n in res)


@pytest.mark.asyncio
async def test_get_note(server):
    res = _extract(await server.call_tool(
        "get_note", {"path": "01-fleeting-notes/topic-thought.md"}
    ))
    assert "deep work" in res.lower()


@pytest.mark.asyncio
async def test_get_guidance(server):
    res = _extract(await server.call_tool(
        "get_guidance", {"topic": "code-review-checklist"}
    ))
    assert "code review" in res.lower()


@pytest.mark.asyncio
async def test_list_projects(server):
    res = _extract(await server.call_tool("list_projects", {}))
    assert any(p["slug"] == "sample-project" for p in res)


@pytest.mark.asyncio
async def test_create_note(server, temp_library):
    res = _extract(await server.call_tool(
        "create_note",
        {"kind": "fleeting", "area_or_path": "", "title": "MCP-built note", "content": "hi"},
    ))
    assert res == "01-fleeting-notes/mcp-built-note.md"
    assert (temp_library / res).read_text() == "hi"


@pytest.mark.asyncio
async def test_update_note(server, temp_library):
    res = _extract(await server.call_tool(
        "update_note",
        {"path": "01-fleeting-notes/topic-thought.md", "content": "rewritten"},
    ))
    assert res == "01-fleeting-notes/topic-thought.md"
    assert (temp_library / res).read_text() == "rewritten"


@pytest.mark.asyncio
async def test_append_fleeting(server, temp_library):
    res = _extract(await server.call_tool(
        "append_fleeting", {"content": "tool-driven append"}
    ))
    assert res.startswith("01-fleeting-notes/")
    assert "tool-driven append" in (temp_library / res).read_text()


@pytest.mark.asyncio
async def test_add_quote(server, temp_library):
    res = _extract(await server.call_tool(
        "add_quote",
        {"source_title": "A Talk", "author": "A Speaker", "text": "Say it plainly.",
         "why": "The house style in three words.", "category": "articles",
         "themes": ["writing"]},
    ))
    assert res == {"path": "02-literature-notes/articles/a-talk.md", "created": True}
    note = (temp_library / res["path"]).read_text()
    assert '> "Say it plainly."' in note
    assert "#quote/writing" in note


@pytest.mark.asyncio
async def test_list_pending_changes(git_server, temp_git_library):
    (temp_git_library / "01-fleeting-notes" / "via-tool.md").write_text("x")
    res = _extract(await git_server.call_tool("list_pending_changes", {}))
    assert any(p["path"] == "01-fleeting-notes/via-tool.md" for p in res)


@pytest.mark.asyncio
async def test_save_changes(git_server, temp_git_library):
    (temp_git_library / "01-fleeting-notes" / "saved.md").write_text("hi")
    res = _extract(await git_server.call_tool(
        "save_changes", {"message": "add saved.md via tool"}
    ))
    assert res["committed"] is True
    assert res["pushed"] is True
    assert res["commit_sha"]


@pytest.mark.asyncio
async def test_teach_tools_round_trip(server, temp_library):
    start = _extract(await server.call_tool("teach_start", {"project": "sample-project"}))
    assert start["exists"] is False and "## Teaching Workspace" in start["instructions"]

    written = _extract(await server.call_tool("write_teach_file", {
        "project": "sample-project",
        "path": "lessons/0001-hello.html",
        "content": "<html><head><title>Hello</title></head><body><p>Hi there</p></body></html>",
    }))
    assert written["url"] == "/knowledge/projects/sample-project/teach/lessons/0001-hello.html"

    await server.call_tool("edit_teach_file", {
        "project": "sample-project", "path": "lessons/0001-hello.html",
        "old": "Hi there", "new": "Hello again",
    })
    lessons = _extract(await server.call_tool("list_lessons", {"project": "sample-project"}))
    assert [lesson["title"] for lesson in lessons] == ["Hello"]
    text = _extract(await server.call_tool("get_lesson", {"path": written["path"]}))
    assert "Hello again" in text
