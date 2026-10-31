"""Teaching workspaces: the `teach` skill served over MCP.

A project's teaching workspace is `05-projects/<project>/teach/`, laid out as
Matt Pocock's `teach` skill expects (see `teach_skill/`). These functions let a
chat that has no skills of its own run that skill: `teach_start` hands over the
instructions and the workspace state, and the write functions store what the
chat produces. Like the rest of `writer.py`, they only touch disk; `save_changes`
is still the only path to git.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

_PROJECTS = "05-projects"
_WORKSPACE = "teach"
_SKILL_DIR = Path(__file__).parent / "teach_skill"

# The preamble comes first so its overrides frame everything after it.
_INSTRUCTION_FILES = (
    "CHAT-PREAMBLE.md",
    "SKILL.md",
    "MISSION-FORMAT.md",
    "RESOURCES-FORMAT.md",
    "LEARNING-RECORD-FORMAT.md",
    "GLOSSARY-FORMAT.md",
)

# PLAN.md is the lesson plan the reading app writes for a book's workspace.
_STATE_FILES = ("MISSION.md", "RESOURCES.md", "NOTES.md", "PLAN.md")
_SUBDIRS = ("lessons", "reference", "learning-records", "assets")

# .json is left out on purpose: the portal's copy step does not publish it.
_ALLOWED_SUFFIXES = {".html", ".css", ".js", ".svg", ".md"}

# Assets larger than this are listed by path only, so teach_start stays small.
_ASSET_INLINE_LIMIT = 40_000

_PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NUMBERED_RE = re.compile(r"^(\d{4})-")


class TeachError(ValueError):
    """A teaching-workspace request that cannot be carried out."""


def load_instructions() -> str:
    """The chat preamble followed by the vendored skill files, as one document."""
    parts = []
    for name in _INSTRUCTION_FILES:
        parts.append(f"<!-- file: {name} -->\n{(_SKILL_DIR / name).read_text()}")
    return "\n\n".join(parts)


def _project_dir(library_root: Path, project: str) -> Path:
    if not _PROJECT_RE.match(project):
        raise TeachError(f"invalid project name: {project!r}; expected a kebab-case folder name")
    path = library_root / _PROJECTS / project
    if not (path / "README.md").is_file():
        raise TeachError(f"no such project: {_PROJECTS}/{project}/README.md does not exist")
    return path


def _workspace(library_root: Path, project: str) -> Path:
    return _project_dir(library_root, project) / _WORKSPACE


def _rel(library_root: Path, path: Path) -> str:
    return path.relative_to(library_root).as_posix()


def published_url(relative_path: str) -> str:
    """The portal URL path for a library file, following the portal's slug rules.

    Other files are copied as-is, so `NN-` prefixes go from directories only. A
    `.md` file becomes an Astro page: lower-cased, `NN-` stripped from every
    segment, `README`/`index` collapsed onto the directory, trailing slash.
    """
    parts = relative_path.split("/")
    dirs = [re.sub(r"^\d+-", "", p) for p in parts[:-1]]
    name = parts[-1]
    if not name.endswith(".md"):
        return "/knowledge/" + "/".join([*dirs, name])
    stem = re.sub(r"^\d+-", "", name[:-3])
    segments = dirs if stem.lower() in ("readme", "index") else [*dirs, stem]
    return "/knowledge/" + "/".join(segments).lower() + "/"


def _workspace_file(library_root: Path, project: str, path: str) -> Path:
    """Resolve `path` inside the workspace, refusing anything the skill would not write."""
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise TeachError(f"path must be relative to the workspace, without '..': {path!r}")
    if rel.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise TeachError(
            f"file type not allowed: {rel.suffix or '(none)'}; expected one of "
            f"{sorted(_ALLOWED_SUFFIXES)}"
        )
    top = rel.parts[0]
    if len(rel.parts) == 1:
        if top not in _STATE_FILES:
            raise TeachError(f"top-level file must be one of {list(_STATE_FILES)}: {path!r}")
    elif top not in _SUBDIRS:
        raise TeachError(f"path must start with one of {list(_SUBDIRS)}: {path!r}")
    workspace = _workspace(library_root, project).resolve()
    full = (workspace / rel).resolve()
    if not full.is_relative_to(workspace):
        raise TeachError(f"path escapes the workspace: {path!r}")
    return full


class _TextExtractor(HTMLParser):
    """Collects readable text and the <title>, skipping scripts and styles."""

    _SKIP = {"script", "style", "noscript", "template"}
    _BLOCK = {"p", "div", "section", "article", "li", "tr", "br", "hr", "pre", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "button", "summary", "figcaption", "td", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.title = ""
        self.h1 = ""
        self._skip_depth = 0
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        if tag in self._BLOCK:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        if tag in self._BLOCK:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        if self._in_h1:
            self.h1 += data
        self.chunks.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.chunks).splitlines())
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _parse_html(html: str) -> _TextExtractor:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser


def list_lessons(library_root: Path, project: str) -> list[dict]:
    """The numbered lessons in a project's workspace, oldest first."""
    lessons_dir = _workspace(library_root, project) / "lessons"
    if not lessons_dir.is_dir():
        return []
    out = []
    for f in sorted(lessons_dir.glob("*.html")):
        m = _NUMBERED_RE.match(f.name)
        parsed = _parse_html(f.read_text())
        rel = _rel(library_root, f)
        out.append({
            "number": int(m.group(1)) if m else None,
            "title": (parsed.title or parsed.h1 or f.stem).strip(),
            "path": rel,
            "url": published_url(rel),
        })
    return out


def get_lesson(library_root: Path, relative_path: str) -> str:
    """The readable text of a lesson or reference page, without markup, scripts or styles."""
    full = (library_root / relative_path).resolve()
    root = library_root.resolve()
    parts = Path(relative_path).parts
    if (
        ".." in parts
        or not full.is_relative_to(root)
        or full.suffix != ".html"
        or len(parts) < 5
        or parts[0] != _PROJECTS
        or parts[2] != _WORKSPACE
    ):
        raise TeachError(
            f"not a workspace page: {relative_path!r}; expected "
            f"{_PROJECTS}/<project>/{_WORKSPACE}/<lessons|reference>/<file>.html"
        )
    if not full.is_file():
        raise TeachError(f"lesson not found: {relative_path}")
    parsed = _parse_html(full.read_text())
    title = (parsed.title or parsed.h1).strip()
    body = parsed.text()
    return f"# {title}\n\n{body}" if title else body


def teach_start(library_root: Path, project: str) -> dict:
    """The skill's instructions plus everything the workspace holds today.

    Lessons and reference pages are listed, not inlined; the chat reads one with
    `get_lesson` only when it needs it. State files, learning records and small
    assets are inlined, because the skill reads them before every lesson.
    """
    workspace = _workspace(library_root, project)

    def read(path: Path) -> str | None:
        return path.read_text() if path.is_file() else None

    records = []
    records_dir = workspace / "learning-records"
    if records_dir.is_dir():
        for f in sorted(records_dir.glob("*.md")):
            records.append({"path": f"learning-records/{f.name}", "content": f.read_text()})

    assets = []
    assets_dir = workspace / "assets"
    if assets_dir.is_dir():
        for f in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
            entry = {"path": f.relative_to(workspace).as_posix()}
            if f.stat().st_size <= _ASSET_INLINE_LIMIT and f.suffix.lower() in _ALLOWED_SUFFIXES:
                entry["content"] = f.read_text()
            assets.append(entry)

    reference = []
    reference_dir = workspace / "reference"
    if reference_dir.is_dir():
        for f in sorted(reference_dir.glob("*.html")):
            rel = _rel(library_root, f)
            reference.append({"path": rel, "url": published_url(rel)})

    return {
        "instructions": load_instructions(),
        "workspace": _rel(library_root, workspace),
        "exists": workspace.is_dir(),
        "project_readme": (workspace.parent / "README.md").read_text(),
        "state": {name: read(workspace / name) for name in _STATE_FILES},
        "learning_records": records,
        "lessons": list_lessons(library_root, project),
        "reference": reference,
        "assets": assets,
    }


def write_teach_file(library_root: Path, project: str, path: str, content: str) -> dict:
    """Create or replace one workspace file. Returns its library path and published URL."""
    full = _workspace_file(library_root, project, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    rel = _rel(library_root, full)
    return {"path": rel, "url": published_url(rel)}


def edit_teach_file(library_root: Path, project: str, path: str, old: str, new: str) -> dict:
    """Replace one exact, unique occurrence of `old` in an existing workspace file."""
    full = _workspace_file(library_root, project, path)
    if not full.is_file():
        raise TeachError(f"cannot edit; file does not exist: {path}")
    text = full.read_text()
    count = text.count(old) if old else 0
    if count != 1:
        raise TeachError(f"`old` must occur exactly once in {path}; found {count}")
    full.write_text(text.replace(old, new, 1))
    rel = _rel(library_root, full)
    return {"path": rel, "url": published_url(rel)}


# ---- Book courses: a lesson plan from the reading app ----------------------------

# A new book workspace copies its components from this one, so its lessons get
# the shared stylesheet, the quiz and the Recall marking from the start.
TEMPLATE_PROJECT = "use-the-system"
# The reading app is on the public gateway, not on the portal site's host.
READER_URL = "https://gateway.kennyrnwilson.com/read/"
_PROJECTS_INDEX = "05-projects/README.md"
_ACTIVE_TABLE = re.compile(r"^## Active Projects\n\n(?:\|.*\n)+", re.MULTILINE)


def _plan_section(heading: str, body: str) -> str:
    return f"## {heading.strip()}\n\n{body.strip()}\n"


def upsert_plan_section(plan: str, heading: str, body: str) -> str:
    """Replace the `## heading` section of PLAN.md, or append it if there is none."""
    section = _plan_section(heading, body)
    pattern = re.compile(rf"^## {re.escape(heading.strip())}\n.*?(?=^## |\Z)",
                         re.MULTILINE | re.DOTALL)
    if pattern.search(plan):
        return pattern.sub(lambda _: section + "\n", plan, count=1).rstrip() + "\n"
    return f"{plan.rstrip()}\n\n{section}"


def _project_readme(title: str, author: str, book_slug: str, today: str) -> str:
    by = f" by {author}" if author else ""
    return f"""---
title: {title}
---
# {title}

← [Back to Projects](../README.md)

**Status:** In progress
**Started:** {today}
**Expected Completion:** when the plan's lessons are done
**Last Updated:** {today}

## Overview

Lessons from the book *{title}*{by}, in
[book-library](book-library/{book_slug}/README.md). The reading app drafted the
[lesson plan](./teach/PLAN.md); the teacher writes each lesson from it. To take
the next one, ask a chat: "teach me the next lesson in the {book_slug} project".

## Lessons

The lessons are listed in the [teaching workspace](./teach/MISSION.md) as they are written.

---

**Related:**
- [Lesson plan](./teach/PLAN.md) — the lessons to write, chapter by chapter
- [Teaching workspace](./teach/MISSION.md) — mission, resources, lessons and records
- [Projects](../README.md) — all active and completed projects

**Tags:** #learning #teach #book

*Created: {today}*
*Last Updated: {today}*
"""


def _mission(title: str, why: str) -> str:
    return f"""# Mission: {title}

## Why
{why.strip()}

## Success looks like
- Kenny explains each chapter in the plan from memory, in his own words.
- Kenny passes each lesson's Recall without looking at the book.

## Constraints
- Each lesson is doable on a phone in about 10 minutes.
- Solo: no communities.
- Lessons teach from the book itself: its text and its chapter summaries in
  book-library, not from the model's memory.

## Out of scope
- Chapters the plan does not list.
"""


def _resources(title: str, author: str, book_slug: str) -> str:
    by = f" by {author}" if author else ""
    return f"""# {title} Resources

## Knowledge

- [Book: *{title}*{by}](/books/{book_slug}/)
  The source for every lesson. Use for: everything. Fetch a chapter's summary
  with the book-library tool `get_chapter_summary`.
- [Read it in the reading app]({READER_URL}#/book/{book_slug})
  The full text, with Kenny's highlights and notes.

## Wisdom (Communities)

Kenny learns solo: do not propose communities.
"""


def _notes(book_slug: str) -> str:
    return f"""# Notes

- This workspace was started by the reading app for the book `{book_slug}`.
  `PLAN.md` lists the lessons to write, chapter by chapter. Teach the first
  lesson in it that has no link yet, then link it there:
  `1. [Lesson title](./lessons/0001-x.html)`.
- Each plan section starts with a "Read it" link into the reading app. Put it
  in the lesson as the primary source.
- Reads on a phone: each lesson is about 10 minutes.
"""


def _plan_header(title: str, book_slug: str) -> str:
    return f"""# Lesson plan: {title}

The lessons to write for [*{title}*](/books/{book_slug}/), drafted in the
reading app. A section per chapter, or one for the whole book. Each lesson
names what Kenny will be able to do, where in the book it comes from, and a
Recall question. A lesson that has been written is a link to it.
"""


def _add_to_projects_index(library_root: Path, title: str, book_slug: str, today: str) -> bool:
    index = library_root / _PROJECTS_INDEX
    if not index.is_file():
        return False
    text = index.read_text()
    link = f"(./{book_slug}/README.md)"
    if link in text:
        return False
    match = _ACTIVE_TABLE.search(text)
    if match is None:
        return False
    row = f"| [{title}]{link} | In progress | {today} | When the lesson plan is done |\n"
    index.write_text(text[: match.end()] + row + text[match.end():])
    return True


def save_lesson_plan(
    library_root: Path,
    book_slug: str,
    title: str,
    author: str,
    section: str,
    plan: str,
    why: str = "",
    today: str | None = None,
) -> dict:
    """Write one section of a book's lesson plan, creating the book's workspace if needed.

    The project is `05-projects/<book_slug>/`. On first use it gets a README, a
    row in the projects index, a teaching workspace with MISSION.md (from
    `why`), RESOURCES.md and NOTES.md, and the components of the template
    workspace. The plan is `teach/PLAN.md`, one `## section` per chapter (or
    one for the whole book); saving a section again replaces it.
    """
    if not _PROJECT_RE.match(book_slug):
        raise TeachError(f"invalid book slug: {book_slug!r}")
    if not section.strip() or "\n" in section:
        raise TeachError("section must be one line, such as the chapter's title")
    if not plan.strip():
        raise TeachError("the plan is empty")
    today = today or date.today().isoformat()
    project = library_root / _PROJECTS / book_slug
    readme = project / "README.md"
    workspace = project / _WORKSPACE
    written: list[Path] = []
    created = not readme.is_file()

    if created:
        if not why.strip():
            raise TeachError("a new book course needs `why`: the reason Kenny is reading the book")
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(_project_readme(title, author, book_slug, today))
        written.append(readme)
        if _add_to_projects_index(library_root, title, book_slug, today):
            written.append(library_root / _PROJECTS_INDEX)
    elif f"book-library/{book_slug}/" not in readme.read_text():
        raise TeachError(
            f"{_PROJECTS}/{book_slug}/ is a project that is not about this book; rename one of them"
        )

    workspace.mkdir(exist_ok=True)
    for name, content in (
        ("MISSION.md", _mission(title, why) if why.strip() else None),
        ("RESOURCES.md", _resources(title, author, book_slug)),
        ("NOTES.md", _notes(book_slug)),
    ):
        path = workspace / name
        if content is not None and not path.is_file():
            path.write_text(content)
            written.append(path)
    if not (workspace / "MISSION.md").is_file():
        raise TeachError("the workspace has no MISSION.md; pass `why` to write one")

    assets = workspace / "assets"
    template_assets = library_root / _PROJECTS / TEMPLATE_PROJECT / _WORKSPACE / "assets"
    if not assets.is_dir() and template_assets.is_dir():
        shutil.copytree(template_assets, assets)
        written.extend(p for p in assets.rglob("*") if p.is_file())

    plan_file = workspace / "PLAN.md"
    current = plan_file.read_text() if plan_file.is_file() else _plan_header(title, book_slug)
    plan_file.write_text(upsert_plan_section(current, section, plan))
    written.append(plan_file)

    paths = sorted({_rel(library_root, p) for p in written})
    plan_rel = _rel(library_root, plan_file)
    return {
        "project": book_slug,
        "created": created,
        "paths": paths,
        "plan": plan_rel,
        "plan_url": published_url(plan_rel),
        "project_url": published_url(_rel(library_root, readme)),
    }
