"""Tests for git_ops."""

from pathlib import Path

from knowledge_library_mcp.git_ops import (
    SaveResult,
    list_pending_changes,
    save_changes,
)


def test_list_pending_changes_clean(temp_git_library: Path):
    pending = list_pending_changes(temp_git_library)
    assert pending == []


def test_list_pending_changes_after_modify(temp_git_library: Path):
    (temp_git_library / "01-fleeting-notes" / "topic-thought.md").write_text("changed")
    (temp_git_library / "01-fleeting-notes" / "new.md").write_text("new note")
    pending = list_pending_changes(temp_git_library)
    statuses = {p["path"]: p["status"] for p in pending}
    assert statuses["01-fleeting-notes/topic-thought.md"] == " M"
    assert statuses["01-fleeting-notes/new.md"] == "??"


def test_save_changes_with_message(temp_git_library: Path):
    (temp_git_library / "01-fleeting-notes" / "x.md").write_text("hello")
    result = save_changes(temp_git_library, message="add x")
    assert isinstance(result, SaveResult)
    assert result.committed is True
    assert result.pushed is True
    assert result.commit_sha
    # working tree clean now
    assert list_pending_changes(temp_git_library) == []


def test_save_changes_no_changes_returns_noop(temp_git_library: Path):
    result = save_changes(temp_git_library, message="nothing")
    assert result.committed is False
    assert result.pushed is False


def test_save_changes_autogenerates_message(temp_git_library: Path):
    (temp_git_library / "01-fleeting-notes" / "x.md").write_text("hello")
    (temp_git_library / "03-permanent-notes" / "professional" / "y.md").write_text("more")
    result = save_changes(temp_git_library, message=None)
    assert result.committed is True
    assert result.message  # non-empty
    # message should mention at least one of the changed paths
    assert "x.md" in result.message or "y.md" in result.message
