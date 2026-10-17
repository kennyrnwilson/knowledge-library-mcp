"""FastMCP server exposing knowledge-library tools."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from knowledge_library_mcp.areas import AREAS
from knowledge_library_mcp.git_ops import list_pending_changes as _list_pending
from knowledge_library_mcp.git_ops import save_changes as _save_changes
from knowledge_library_mcp.notes import (
    NoteNotFound,
    get_guidance as _get_guidance,
    get_note as _get_note,
    list_permanent_notes as _list_permanent,
    list_projects as _list_projects,
)
from knowledge_library_mcp.search import search_notes as _search
from knowledge_library_mcp.teach import (
    edit_teach_file as _edit_teach_file,
    get_lesson as _get_lesson,
    list_lessons as _list_lessons,
    teach_start as _teach_start,
    write_teach_file as _write_teach_file,
)
from knowledge_library_mcp.writer import (
    NoteAlreadyExists,
    NoteNotFoundForUpdate,
    append_fleeting as _append_fleeting,
    create_note as _create_note,
    update_note as _update_note,
)


def _resolve_library_root() -> Path:
    env = os.environ.get("KNOWLEDGE_LIBRARY_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def build_server(host: str = "127.0.0.1", port: int = 5103) -> FastMCP:
    library_root = _resolve_library_root()
    mcp = FastMCP("knowledge-library", host=host, port=port)

    # ---- Read tools ------------------------------------------------------------

    @mcp.tool()
    def list_areas() -> list[str]:
        """The six canonical areas of the knowledge library."""
        return list(AREAS)

    @mcp.tool()
    def search_notes(query: str, area: str | None = None) -> list[dict]:
        """Full-text search across the library. Optional `area` scopes to permanent/guidance for that area."""
        return [
            {"path": h.path, "line": h.line_number, "text": h.line}
            for h in _search(library_root, query, area=area)
        ]

    @mcp.tool()
    def get_note(path: str) -> str:
        """Return the markdown content of a note by relative path."""
        try:
            return _get_note(library_root, path)
        except NoteNotFound as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def list_permanent_notes(area: str) -> list[dict]:
        """List all permanent notes within one area."""
        return _list_permanent(library_root, area)

    @mcp.tool()
    def get_guidance(topic: str) -> str:
        """Return the markdown of `04-guidance/<area>/<topic>.md` for the first matching area."""
        try:
            return _get_guidance(library_root, topic)
        except NoteNotFound as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def list_projects() -> list[dict]:
        """List active projects (directories under `05-projects/` containing a README.md)."""
        return _list_projects(library_root)

    # ---- Write tools (filesystem only — no git side-effects) -------------------

    @mcp.tool()
    def create_note(kind: str, area_or_path: str, title: str, content: str) -> str:
        """Create a new note. Returns relative path. Refuses to overwrite.

        kind: fleeting | literature | permanent | guidance | project
        area_or_path: required area name for permanent/guidance; optional sub-path for others.
        """
        try:
            return _create_note(library_root, kind=kind, area_or_path=area_or_path,
                                title=title, content=content)
        except NoteAlreadyExists as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def update_note(path: str, content: str) -> str:
        """Overwrite an existing note. Refuses if path doesn't already exist."""
        try:
            return _update_note(library_root, path, content)
        except NoteNotFoundForUpdate as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def append_fleeting(content: str) -> str:
        """Append a timestamped block to today's `01-fleeting-notes/YYYY-MM-DD.md`. Lowest-friction capture."""
        return _append_fleeting(library_root, content)

    # ---- Teaching tools (the `teach` skill over MCP; filesystem only) ----------

    @mcp.tool()
    def teach_start(project: str) -> dict:
        """Start or continue teaching the user a subject, in `05-projects/<project>/teach/`.

        Call this first whenever the user asks to be taught, or for the next lesson.
        Returns the `teach` skill's instructions (follow them) plus the workspace's
        mission, notes, learning records, assets, and the lessons so far.
        """
        return _teach_start(library_root, project)

    @mcp.tool()
    def list_lessons(project: str) -> list[dict]:
        """List a project's lessons: number, title, library path and published URL."""
        return _list_lessons(library_root, project)

    @mcp.tool()
    def get_lesson(path: str) -> str:
        """Return the readable text of a lesson or reference page (no markup), by library path."""
        return _get_lesson(library_root, path)

    @mcp.tool()
    def write_teach_file(project: str, path: str, content: str) -> dict:
        """Create or replace a file in a project's teaching workspace. Does not commit.

        path is relative to the workspace: MISSION.md, RESOURCES.md, NOTES.md, or a file
        under lessons/, reference/, learning-records/ or assets/. Allowed types: .html,
        .css, .js, .svg, .md. Returns the library path and the published URL.
        """
        return _write_teach_file(library_root, project, path, content)

    @mcp.tool()
    def edit_teach_file(project: str, path: str, old: str, new: str) -> dict:
        """Replace one exact, unique piece of text in a workspace file. Does not commit.

        Prefer this to write_teach_file for small fixes: it avoids resending the whole file.
        """
        return _edit_teach_file(library_root, project, path, old, new)

    # ---- Git tools (explicit-save model) ---------------------------------------

    @mcp.tool()
    def list_pending_changes() -> list[dict]:
        """Return uncommitted changes in the knowledge-library (parsed git status)."""
        return _list_pending(library_root)

    @mcp.tool()
    def save_changes(message: str | None = None) -> dict:
        """Stage all changes, commit, push origin main.

        ONLY call this tool when the user has explicitly approved the change
        ("save it", "commit that", "looks good, push it"). Drafts iterated in
        chat without explicit approval should remain uncommitted on disk.
        """
        result = _save_changes(library_root, message=message)
        return {
            "committed": result.committed,
            "pushed": result.pushed,
            "commit_sha": result.commit_sha,
            "message": result.message,
            "pending_count": len(result.pending),
        }

    return mcp
