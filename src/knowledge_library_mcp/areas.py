"""Canonical areas of the knowledge library and helpers."""

from __future__ import annotations

from pathlib import PurePosixPath

AREAS: tuple[str, ...] = (
    "professional",
    "wellbeing",
    "productivity",
    "parenting",
    "leisure",
    "personal-development",
)
_AREAS_SET = set(AREAS)

_AREA_PARENT_DIRS = ("03-permanent-notes", "04-guidance")


def area_for_path(relative_path: str) -> str | None:
    """Return the area name for `relative_path` if it lies under one of the
    area-aware parent dirs (03-permanent-notes/, 04-guidance/) and the immediate
    subfolder is a known area; otherwise None.
    """
    parts = PurePosixPath(relative_path).parts
    if len(parts) < 2:
        return None
    if parts[0] not in _AREA_PARENT_DIRS:
        return None
    candidate = parts[1]
    return candidate if candidate in _AREAS_SET else None
