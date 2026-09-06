"""Filesystem readers over the knowledge-library tree."""

from __future__ import annotations

from pathlib import Path

from knowledge_library_mcp.areas import AREAS


class NoteNotFound(Exception):
    """Raised when a requested note does not exist on disk."""


def _safe_resolve(library_root: Path, relative_path: str) -> Path:
    """Resolve `relative_path` under `library_root`, blocking traversal outside the root."""
    candidate = (library_root / relative_path).resolve()
    root_resolved = library_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise ValueError(f"path escapes library root: {relative_path!r}") from e
    return candidate


def get_note(library_root: Path, relative_path: str) -> str:
    """Return the text of a note at `relative_path` under `library_root`."""
    full = _safe_resolve(library_root, relative_path)
    if not full.is_file():
        raise NoteNotFound(f"note not found: {relative_path}")
    return full.read_text()


def list_permanent_notes(library_root: Path, area: str) -> list[dict]:
    """Return all notes under `03-permanent-notes/<area>/`."""
    if area not in AREAS:
        raise ValueError(f"unknown area: {area!r}; expected one of {AREAS}")
    base = library_root / "03-permanent-notes" / area
    if not base.is_dir():
        return []
    out: list[dict] = []
    for md in sorted(base.rglob("*.md")):
        rel = md.relative_to(library_root)
        out.append({
            "path": rel.as_posix(),
            "title": md.stem,
            "area": area,
        })
    return out


def list_projects(library_root: Path) -> list[dict]:
    """List active projects under `05-projects/` (directories with a README.md)."""
    base = library_root / "05-projects"
    if not base.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        readme = child / "README.md"
        if readme.is_file():
            out.append({"slug": child.name, "readme": (readme.relative_to(library_root)).as_posix()})
    return out


def get_guidance(library_root: Path, topic: str) -> str:
    """Return the markdown of `04-guidance/<subdir>/<topic>.md`, searching all subdirectories."""
    if "/" in topic or "\\" in topic or topic.startswith(".") or not topic:
        raise ValueError(f"invalid topic: {topic!r}")
    base = library_root / "04-guidance"
    if not base.is_dir():
        raise NoteNotFound("guidance dir missing")
    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir():
            continue
        candidate = subdir / f"{topic}.md"
        if candidate.is_file():
            return candidate.read_text()
    raise NoteNotFound(f"guidance topic not found: {topic}")
