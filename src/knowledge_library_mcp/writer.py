"""Filesystem-only write tools for the knowledge library.

These tools NEVER commit. The MCP server's `save_changes` tool is the only
path from disk to git history. See spec § 8.2 (explicit-save model).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

class NoteAlreadyExists(Exception):
    """create_note refuses to overwrite an existing file."""


class NoteNotFoundForUpdate(Exception):
    """update_note refuses to create a new file."""


_KIND_PARENT = {
    "fleeting": "01-fleeting-notes",
    "literature": "02-literature-notes",
    "permanent": "03-permanent-notes",
    "guidance": "04-guidance",
    "project": "05-projects",
}

_KIND_REQUIRES_AREA = {"permanent", "guidance"}


def slugify(title: str) -> str:
    """Lower-case kebab-case slug. Strips non-alphanumerics; collapses separators.

    Apostrophes and quote-like characters are removed (not converted to dashes),
    so "Don't" -> "dont" rather than "don-t".
    """
    s = title.lower()
    # Drop apostrophes / quote-like marks so contractions don't become dashed.
    s = re.sub(r"['’‘\"`]+", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        raise ValueError(f"slugify produced an empty slug from {title!r}")
    return s


def _safe_join(library_root: Path, *parts: str) -> Path:
    candidate = library_root.joinpath(*parts).resolve()
    root_resolved = library_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise ValueError(f"path escapes library root: {parts!r}") from e
    return candidate


def _kind_path(kind: str, area_or_path: str, slug: str) -> Path:
    """Compose the relative path under `library_root` for a given kind/slug."""
    if kind not in _KIND_PARENT:
        raise ValueError(f"unknown kind: {kind!r}; expected one of {sorted(_KIND_PARENT)}")
    parent = _KIND_PARENT[kind]

    if kind in _KIND_REQUIRES_AREA:
        sub = area_or_path.strip().strip("/")
        if not sub:
            raise ValueError(
                f"kind={kind!r} requires a non-empty area_or_path (area name or sub-path)"
            )
        return Path(parent) / sub / f"{slug}.md"

    if kind == "project":
        # Project = a directory containing README.md, optionally nested under a sub-path.
        sub = area_or_path.strip().strip("/")
        if sub:
            return Path(parent) / sub / slug / "README.md"
        return Path(parent) / slug / "README.md"

    # fleeting / literature: optional sub-path, file = <slug>.md
    sub = area_or_path.strip().strip("/")
    if sub:
        return Path(parent) / sub / f"{slug}.md"
    return Path(parent) / f"{slug}.md"


def create_note(
    library_root: Path,
    kind: str,
    area_or_path: str,
    title: str,
    content: str,
) -> str:
    """Create a new note. Returns the relative path. Refuses to overwrite."""
    slug = slugify(title)
    rel = _kind_path(kind, area_or_path, slug)
    full = _safe_join(library_root, str(rel))
    if full.exists():
        raise NoteAlreadyExists(f"refusing to overwrite existing file: {rel.as_posix()}")
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return rel.as_posix()


def update_note(library_root: Path, relative_path: str, content: str) -> str:
    """Overwrite an existing note. Refuses if path doesn't exist."""
    full = _safe_join(library_root, relative_path)
    if not full.is_file():
        raise NoteNotFoundForUpdate(f"cannot update; note does not exist: {relative_path}")
    full.write_text(content)
    return relative_path


def append_fleeting(library_root: Path, content: str) -> str:
    """Append a timestamped block to today's `01-fleeting-notes/YYYY-MM-DD.md`.

    Creates the file with a `# YYYY-MM-DD` heading on first use of the day.
    Each appended block is prefixed with `## HH:MM:SS`.
    """
    # Use the timezone-aware datetime as returned by datetime.now(); we do not
    # convert via astimezone() because tests pin a fake "now" with a specific
    # tzinfo and expect that exact wall-clock time on disk.
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    rel = Path("01-fleeting-notes") / f"{date_str}.md"
    full = _safe_join(library_root, str(rel))
    full.parent.mkdir(parents=True, exist_ok=True)
    block = f"\n\n## {time_str}\n\n{content}\n"
    if full.is_file():
        with full.open("a") as fh:
            fh.write(block)
    else:
        with full.open("w") as fh:
            fh.write(f"# {date_str}{block}")
    return rel.as_posix()
