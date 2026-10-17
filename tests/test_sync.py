"""Keeping the server's clone in step with origin: refresh and save_changes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from knowledge_library_mcp import git_ops
from knowledge_library_mcp.git_ops import refresh, save_changes


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    monkeypatch.setattr(git_ops, "REFRESH_INTERVAL", 0.0)
    git_ops._last_refresh.clear()


@pytest.fixture
def other_clone(temp_git_library: Path) -> Path:
    """A second clone, standing in for the Air or GitHub pushing to main."""
    other = temp_git_library.parent / "other"
    subprocess.run(
        ["git", "clone", str(temp_git_library.parent / "origin.git"), str(other)],
        check=True, capture_output=True,
    )
    _git(other, "config", "user.email", "other@example.com")
    _git(other, "config", "user.name", "Other")
    return other


def _push_from(clone: Path, rel: str, text: str) -> None:
    (clone / rel).write_text(text)
    _git(clone, "add", "-A")
    _git(clone, "commit", "-m", f"edit {rel}")
    _git(clone, "push", "origin", "main")


def _origin_head(library: Path) -> str:
    return _git(library.parent / "origin.git", "log", "-1", "--format=%s", "main")


def test_refresh_fast_forwards_to_origin(temp_git_library, other_clone):
    _push_from(other_clone, "01-fleeting-notes/from-air.md", "from the Air")
    assert refresh(temp_git_library) is True
    assert (temp_git_library / "01-fleeting-notes" / "from-air.md").read_text() == "from the Air"


def test_refresh_is_throttled(temp_git_library, other_clone, monkeypatch):
    monkeypatch.setattr(git_ops, "REFRESH_INTERVAL", 3600.0)
    refresh(temp_git_library)
    _push_from(other_clone, "01-fleeting-notes/later.md", "later")
    assert refresh(temp_git_library) is False
    assert not (temp_git_library / "01-fleeting-notes" / "later.md").exists()


def test_refresh_is_a_no_op_outside_git(temp_library):
    assert refresh(temp_library) is False


def test_refresh_and_save_leave_other_branches_alone(temp_git_library, other_clone):
    _git(temp_git_library, "checkout", "-b", "feature")
    _push_from(other_clone, "01-fleeting-notes/from-air.md", "from the Air")
    assert refresh(temp_git_library) is False
    assert not (temp_git_library / "01-fleeting-notes" / "from-air.md").exists()
    (temp_git_library / "01-fleeting-notes" / "draft.md").write_text("draft")
    with pytest.raises(RuntimeError, match="only runs with `main`"):
        save_changes(temp_git_library)
    assert _origin_head(temp_git_library) == "edit 01-fleeting-notes/from-air.md"


def test_save_rebases_onto_newer_origin(temp_git_library, other_clone):
    _push_from(other_clone, "01-fleeting-notes/from-air.md", "from the Air")
    (temp_git_library / "01-fleeting-notes" / "mine.md").write_text("mine")
    result = save_changes(temp_git_library, message="add mine")
    assert result.pushed is True
    assert _origin_head(temp_git_library) == "add mine"
    assert (temp_git_library / "01-fleeting-notes" / "from-air.md").exists()


def test_save_conflict_keeps_commit_local_and_aborts_rebase(temp_git_library, other_clone):
    note = "01-fleeting-notes/topic-thought.md"
    _push_from(other_clone, note, "their version")
    (temp_git_library / note).write_text("my version")
    with pytest.raises(RuntimeError, match="conflict with newer commits"):
        save_changes(temp_git_library, message="my edit")
    assert _git(temp_git_library, "log", "-1", "--format=%s") == "my edit"
    assert _git(temp_git_library, "status", "--porcelain") == ""
    assert not (temp_git_library / ".git" / "rebase-merge").exists()
    assert _origin_head(temp_git_library) == f"edit {note}"


def test_save_pushes_a_commit_stranded_by_an_earlier_failure(temp_git_library):
    (temp_git_library / "01-fleeting-notes" / "stranded.md").write_text("x")
    _git(temp_git_library, "add", "-A")
    _git(temp_git_library, "commit", "-m", "stranded")
    result = save_changes(temp_git_library)
    assert result.committed is False and result.pushed is True
    assert _origin_head(temp_git_library) == "stranded"


@pytest.mark.asyncio
async def test_read_tools_see_pushes_made_elsewhere(temp_git_library, other_clone, monkeypatch):
    from knowledge_library_mcp.server import build_server

    monkeypatch.setenv("KNOWLEDGE_LIBRARY_ROOT", str(temp_git_library))
    server = build_server()
    _push_from(other_clone, "01-fleeting-notes/from-air.md", "from the Air")
    await server.call_tool("get_note", {"path": "01-fleeting-notes/from-air.md"})
    assert (temp_git_library / "01-fleeting-notes" / "from-air.md").exists()
