"""FastMCP server exposing knowledge-library tools."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from knowledge_library_mcp.areas import AREAS
from knowledge_library_mcp.git_ops import list_pending_changes as _list_pending
from knowledge_library_mcp.git_ops import refresh as _refresh
from knowledge_library_mcp.git_ops import save_changes as _save_changes
from knowledge_library_mcp.notes import (
    NoteNotFound,
    get_guidance as _get_guidance,
    get_note as _get_note,
    list_fleeting as _list_fleeting,
    list_permanent_notes as _list_permanent,
    list_projects as _list_projects,
)
from knowledge_library_mcp.quotes import add_quote as _add_quote
from knowledge_library_mcp.reading import add_literature_section as _add_literature_section
from knowledge_library_mcp.reading import source_annotations as _source_annotations
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
        _refresh(library_root)
        return [
            {"path": h.path, "line": h.line_number, "text": h.line}
            for h in _search(library_root, query, area=area)
        ]

    @mcp.tool()
    def get_note(path: str) -> str:
        """Return the markdown content of a note by relative path."""
        _refresh(library_root)
        try:
            return _get_note(library_root, path)
        except NoteNotFound as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def list_permanent_notes(area: str) -> list[dict]:
        """List all permanent notes within one area."""
        _refresh(library_root)
        return _list_permanent(library_root, area)

    @mcp.tool()
    def get_guidance(topic: str) -> str:
        """Return the markdown of `04-guidance/<area>/<topic>.md` for the first matching area."""
        _refresh(library_root)
        try:
            return _get_guidance(library_root, topic)
        except NoteNotFound as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def list_fleeting() -> list[dict]:
        """List the inbox: every note under `01-fleeting-notes/`, with its line count and first line."""
        _refresh(library_root)
        return _list_fleeting(library_root)

    @mcp.tool()
    def list_projects() -> list[dict]:
        """List active projects (directories under `05-projects/` containing a README.md)."""
        _refresh(library_root)
        return _list_projects(library_root)

    # ---- Write tools (filesystem only — no git side-effects) -------------------

    @mcp.tool()
    def create_note(kind: str, area_or_path: str, title: str, content: str) -> str:
        """Create a new note. Returns relative path. Refuses to overwrite.

        kind: fleeting | literature | permanent | guidance | project
        area_or_path: required area name for permanent/guidance; optional sub-path for others.
        """
        _refresh(library_root)
        try:
            return _create_note(library_root, kind=kind, area_or_path=area_or_path,
                                title=title, content=content)
        except NoteAlreadyExists as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def update_note(path: str, content: str) -> str:
        """Overwrite an existing note. Refuses if path doesn't already exist."""
        _refresh(library_root)
        try:
            return _update_note(library_root, path, content)
        except NoteNotFoundForUpdate as e:
            raise ValueError(str(e)) from e

    @mcp.tool()
    def append_fleeting(content: str, anchor: str = "") -> str:
        """Append a timestamped block to today's `01-fleeting-notes/YYYY-MM-DD.md`. Lowest-friction capture."""
        _refresh(library_root)
        return _append_fleeting(library_root, content, anchor=anchor)

    @mcp.tool()
    def add_quote(
        source_title: str,
        author: str,
        text: str,
        why: str,
        location: str = "",
        category: str = "books",
        themes: list[str] | None = None,
        links: list[str] | None = None,
        said_by: str = "",
        anchor: str = "",
    ) -> dict:
        """File a quote in its source's literature note, `02-literature-notes/<category>/`.

        Creates the note if none exists, and links it from the folder's README. Writes
        the quote, a source line (author, title, location such as "ch. 11, p. 213"),
        a "Why" line and links plus one `#quote/<theme>` tag per theme. When the
        source quotes someone else, put that person in `said_by`.

        The "Why" and the themes are the user's. Pass the user's words exactly, with
        no corrections. If the user has not given them, or has sent a placeholder
        such as "<your own sentence>", ask; never write them yourself.

        For a book that has its own folder in book-library, use the book-library
        server's `add_book_quote` instead: its notes live there. Do not say that a
        book contains a quote unless a search of that book shows it.
        """
        _refresh(library_root)
        return _add_quote(library_root, source_title=source_title, author=author, text=text,
                          why=why, location=location, category=category, themes=themes,
                          links=links, said_by=said_by, anchor=anchor)

    @mcp.tool()
    def add_literature_section(
        book_slug: str,
        title: str,
        author: str,
        text: str,
        location: str = "",
        passage: str = "",
        anchor: str = "",
    ) -> dict:
        """Add a note in the user's own words to a book's literature note.

        The note is `02-literature-notes/books/<book_slug>.md`, created from the
        literature-summary template if missing; the section goes under its
        reading notes, headed by `location` (such as "ch. 3") and today's date,
        after the `passage` it is about if given. `book_slug` is the book's
        folder name in book-library. `anchor` is an EPUB CFI from the reading app.
        """
        _refresh(library_root)
        return _add_literature_section(library_root, book_slug=book_slug, title=title,
                                       author=author, text=text, location=location,
                                       passage=passage, anchor=anchor)

    @mcp.tool()
    def get_source_annotations(book_slug: str) -> dict:
        """Return everything the knowledge library holds about one book.

        The book's literature note's quotes and reading notes, and every
        fleeting-note block that links to `book-library/<book_slug>/`, each with
        its EPUB anchor where it has one.
        """
        _refresh(library_root)
        return _source_annotations(library_root, book_slug)

    # ---- Teaching tools (the `teach` skill over MCP; filesystem only) ----------

    @mcp.tool()
    def teach_start(project: str) -> dict:
        """Start or continue teaching the user a subject, in `05-projects/<project>/teach/`.

        Call this first whenever the user asks to be taught, or for the next lesson.
        Returns the `teach` skill's instructions (follow them) plus the workspace's
        mission, notes, learning records, assets, and the lessons so far.
        """
        _refresh(library_root)
        return _teach_start(library_root, project)

    @mcp.tool()
    def list_lessons(project: str) -> list[dict]:
        """List a project's lessons: number, title, library path and published URL."""
        _refresh(library_root)
        return _list_lessons(library_root, project)

    @mcp.tool()
    def get_lesson(path: str) -> str:
        """Return the readable text of a lesson or reference page (no markup), by library path."""
        _refresh(library_root)
        return _get_lesson(library_root, path)

    @mcp.tool()
    def write_teach_file(project: str, path: str, content: str) -> dict:
        """Create or replace a file in a project's teaching workspace. Does not commit.

        path is relative to the workspace: MISSION.md, RESOURCES.md, NOTES.md, or a file
        under lessons/, reference/, learning-records/ or assets/. Allowed types: .html,
        .css, .js, .svg, .md. Returns the library path and the published URL.
        """
        _refresh(library_root)
        return _write_teach_file(library_root, project, path, content)

    @mcp.tool()
    def edit_teach_file(project: str, path: str, old: str, new: str) -> dict:
        """Replace one exact, unique piece of text in a workspace file. Does not commit.

        Prefer this to write_teach_file for small fixes: it avoids resending the whole file.
        """
        _refresh(library_root)
        return _edit_teach_file(library_root, project, path, old, new)

    # ---- Git tools (explicit-save model) ---------------------------------------

    @mcp.tool()
    def list_pending_changes() -> list[dict]:
        """Return uncommitted changes in the knowledge-library (parsed git status)."""
        _refresh(library_root)
        return _list_pending(library_root)

    @mcp.tool()
    def save_changes(message: str | None = None, paths: list[str] | None = None) -> dict:
        """Stage changes, commit, push origin main.

        With `paths` (library-relative), only changes under them are committed
        and other drafts stay on disk.

        ONLY call this tool when the user has explicitly approved the change
        ("save it", "commit that", "looks good, push it"). Drafts iterated in
        chat without explicit approval should remain uncommitted on disk.
        """
        result = _save_changes(library_root, message=message, paths=paths)
        return {
            "committed": result.committed,
            "pushed": result.pushed,
            "commit_sha": result.commit_sha,
            "message": result.message,
            # What is still uncommitted after the save, not what the save committed.
            "pending_count": len(_list_pending(library_root)),
        }

    return mcp
