"""Ripgrep wrapper for full-text search across the knowledge library."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from knowledge_library_mcp.areas import AREAS

# Search across these top-level dirs (skips internal/.git/etc).
_DEFAULT_SEARCH_ROOTS = (
    "01-fleeting-notes",
    "02-literature-notes",
    "03-permanent-notes",
    "04-guidance",
    "05-projects",
    "06-tracking",
    "07-archive",
)

_RG_FALLBACK_PATHS = (
    "/opt/homebrew/bin/rg",
    "/usr/local/bin/rg",
)


def _resolve_rg() -> str | None:
    rg = shutil.which("rg")
    if rg:
        return rg
    for candidate in _RG_FALLBACK_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


@dataclass(frozen=True)
class SearchHit:
    path: str          # relative to library_root, posix-style
    line_number: int
    line: str


def search_notes(
    library_root: Path,
    query: str,
    area: str | None = None,
    max_results: int = 50,
) -> list[SearchHit]:
    """Ripgrep across markdown/txt files in the library."""
    if not query.strip():
        return []
    if area is not None and area not in AREAS:
        raise ValueError(f"unknown area: {area!r}; expected one of {AREAS}")

    rg = _resolve_rg()
    if rg is None:
        raise RuntimeError("ripgrep (`rg`) not found on PATH or in /opt/homebrew/bin, /usr/local/bin")

    if area:
        roots = [
            library_root / "03-permanent-notes" / area,
            library_root / "04-guidance" / area,
        ]
        roots = [r for r in roots if r.is_dir()]
    else:
        roots = [library_root / r for r in _DEFAULT_SEARCH_ROOTS if (library_root / r).is_dir()]

    if not roots:
        return []

    cmd = [
        rg,
        "--no-heading", "--line-number",
        "--max-count", str(max_results),
        "--type-add", "doc:*.md",
        "--type-add", "doc:*.txt",
        "--type", "doc",
        "--", query,
        *[str(r) for r in roots],
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed: {proc.stderr.strip()}")

    library_resolved = library_root.resolve()
    hits: list[SearchHit] = []
    for raw in proc.stdout.splitlines():
        try:
            path_str, line_no_str, line = raw.split(":", 2)
        except ValueError:
            continue
        try:
            rel = Path(path_str).resolve().relative_to(library_resolved)
        except ValueError:
            continue
        hits.append(SearchHit(path=rel.as_posix(), line_number=int(line_no_str), line=line))
        if len(hits) >= max_results:
            break
    return hits
